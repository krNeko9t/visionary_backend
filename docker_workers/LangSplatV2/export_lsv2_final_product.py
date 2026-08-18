#!/usr/bin/env python
"""
导出 LangSplatV2 的“最终产物”（不依赖渲染 weight-map）：

1) PLY（每点）：
   - 默认导出“3DGS / Supersplat 兼容”字段：x/y/z, nx/ny/nz, f_dc_*, f_rest_*, opacity, scale_*, rot_*
   - 并追加 extra 属性：weight_0..weight_63: float32（来自每个 GS 的 language logits -> softmax；可选 top-k 稀疏化）

2) Codebook：
   - 二进制 .bin（Float32Array），长度 64*512（row-major）

3) Query 列表：
   - JSON: {"queries":[{"name":"elephant","vector":[...512 floats...]}]}
   - text embedding 使用 OpenCLIPNetwork（与仓库其它可视化脚本一致，默认归一化）
"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
from plyfile import PlyData, PlyElement

from eval.openclip_encoder import OpenCLIPNetwork


def _resolve_ckpt_dir(ckpt_root: str, ckpt_prefix: str, level: int) -> Path:
    root = Path(ckpt_root)
    cand1 = root / f"{ckpt_prefix}_{level}"
    if cand1.exists():
        return cand1

    cand2 = root / ckpt_prefix
    if cand2.exists():
        return cand2

    pattern = f"{ckpt_prefix}_*"
    matches = sorted([p for p in root.glob(pattern) if p.is_dir() and str(p.name).endswith(f"_{level}")])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise FileNotFoundError(
            f"找到多个候选 checkpoint 目录（请检查 --ckpt_prefix 是否更精确）：{[str(m) for m in matches[:10]]}"
        )
    raise FileNotFoundError(f"找不到 checkpoint 目录：{cand1} 或 {cand2}（root={root}）")


def _resolve_level_model_dir(model_root: Path, level: int) -> Path:
    level_dir = Path(f"{model_root}_{level}")
    if level_dir.is_dir():
        return level_dir
    raise FileNotFoundError(f"找不到 level {level} 模型目录: {level_dir}")


def _infer_scene_id_from_ckpt_prefix(ckpt_prefix: str) -> str:
    s = str(ckpt_prefix)
    if "_" not in s:
        return s
    return s.rsplit("_", 1)[0]


def _construct_3dgs_attribute_names(
    features_dc: torch.Tensor,
    features_rest: torch.Tensor,
    scaling: torch.Tensor,
    rotation: torch.Tensor,
) -> List[str]:
    l = ["x", "y", "z", "nx", "ny", "nz"]
    for i in range(int(features_dc.shape[1] * features_dc.shape[2])):
        l.append(f"f_dc_{i}")
    for i in range(int(features_rest.shape[1] * features_rest.shape[2])):
        l.append(f"f_rest_{i}")
    l.append("opacity")
    for i in range(int(scaling.shape[1])):
        l.append(f"scale_{i}")
    for i in range(int(rotation.shape[1])):
        l.append(f"rot_{i}")
    return l


def _write_gaussian_ply_with_extra_from_tensors(
    *,
    xyz: torch.Tensor,
    features_dc: torch.Tensor,
    features_rest: torch.Tensor,
    opacity: torch.Tensor,
    scaling: torch.Tensor,
    rotation: torch.Tensor,
    extra_f4: dict,
    out_path: Path,
    text: bool = False,
):
    xyz_np = xyz.detach().cpu().numpy().astype(np.float32)
    p_count = int(xyz_np.shape[0])
    normals = np.zeros_like(xyz_np, dtype=np.float32)

    f_dc = (
        features_dc.detach()
        .transpose(1, 2)
        .flatten(start_dim=1)
        .contiguous()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    f_rest = (
        features_rest.detach()
        .transpose(1, 2)
        .flatten(start_dim=1)
        .contiguous()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    opacities = opacity.detach().cpu().numpy().astype(np.float32)
    scale = scaling.detach().cpu().numpy().astype(np.float32)
    rot = rotation.detach().cpu().numpy().astype(np.float32)

    attributes_base = np.concatenate((xyz_np, normals, f_dc, f_rest, opacities, scale, rot), axis=1)
    names_base = _construct_3dgs_attribute_names(features_dc, features_rest, scaling, rotation)
    dtype_base = [(name, "f4") for name in names_base]

    extra_names = sorted(list(extra_f4.keys()))
    extra_cols = []
    dtype_extra = []
    for name in extra_names:
        v = extra_f4[name]
        if isinstance(v, torch.Tensor):
            v = v.detach().cpu().numpy()
        v = np.asarray(v)
        if v.ndim == 1:
            v = v.reshape(-1, 1)
        if v.shape[0] != p_count:
            raise ValueError(f"extra[{name}] P mismatch: {v.shape[0]} vs {p_count}")
        v = v.astype(np.float32)
        extra_cols.append(v)
        for c in range(int(v.shape[1])):
            prop_name = name if v.shape[1] == 1 else f"{name}_{c}"
            dtype_extra.append((prop_name, "f4"))

    dtype_full = dtype_base + dtype_extra
    elements = np.empty(p_count, dtype=dtype_full)

    if len(extra_cols) > 0:
        extras_concat = np.concatenate(extra_cols, axis=1)
        attributes_full = np.concatenate((attributes_base, extras_concat), axis=1)
    else:
        attributes_full = attributes_base

    elements[:] = list(map(tuple, attributes_full))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(elements, "vertex")], text=text).write(str(out_path))


def _compute_weights_64(
    logits: torch.Tensor,
    *,
    topk: int,
    require_single_level: bool = True,
) -> torch.Tensor:
    p_count, lk = logits.shape
    k = 64
    if lk % k != 0:
        raise ValueError(f"logits 维度不是 64 的整数倍：LK={lk}")
    level_count = lk // k
    if require_single_level and level_count != 1:
        raise ValueError(f"当前 checkpoint 的 level 数 L={level_count}，但你要求导出固定 64 维权重。请指定单 level 的 ckpt。")

    layer_logits = logits[:, 0:k]
    if topk is not None and int(topk) > 0 and int(topk) < k:
        from utils.vq_utils import softmax_to_topk_soft_code

        w = softmax_to_topk_soft_code(layer_logits, int(topk))
    else:
        w = layer_logits.softmax(dim=1)
    return w.to(torch.float32)


def _write_codebook_bin(codebook_64x512: np.ndarray, out_path: Path):
    if codebook_64x512.shape != (64, 512):
        raise ValueError(f"codebook 必须是 [64,512]，实际 {codebook_64x512.shape}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    codebook_64x512.astype("<f4").reshape(-1).tofile(str(out_path))


def _write_queries_json(queries: List[str], out_path: Path, device: torch.device):
    if len(queries) == 0:
        return

    clip_model = OpenCLIPNetwork(device)
    clip_model.set_positives(list(queries))
    embeds = clip_model.pos_embeds.detach().to(torch.float32).cpu().numpy()

    payload = {"queries": []}
    for name, vec in zip(queries, embeds):
        payload["queries"].append({"name": str(name), "vector": vec.astype(np.float32).tolist()})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def _export_level_checkpoint(*, ckpt_path: Path, level: int, out_root: Path, topk: int) -> None:
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"找不到 checkpoint 文件：{ckpt_path}")

    ckpt = torch.load(str(ckpt_path), map_location="cpu")
    if not (isinstance(ckpt, (tuple, list)) and len(ckpt) == 2):
        raise ValueError(f"未知 checkpoint 格式：{type(ckpt)}")
    model_params, _ = ckpt
    if not (isinstance(model_params, (tuple, list)) and len(model_params) == 14):
        raise ValueError(
            f"checkpoint 里没有 language feature（期望 model_params 长度=14），"
            f"实际 len={len(model_params) if isinstance(model_params, (tuple, list)) else 'N/A'}"
        )

    active_sh_degree = int(model_params[0])
    xyz_t = torch.as_tensor(model_params[1]).detach().to(torch.float32)
    f_dc_t = torch.as_tensor(model_params[2]).detach().to(torch.float32)
    f_rest_t = torch.as_tensor(model_params[3]).detach().to(torch.float32)
    scaling_t = torch.as_tensor(model_params[4]).detach().to(torch.float32)
    rotation_t = torch.as_tensor(model_params[5]).detach().to(torch.float32)
    opacity_t = torch.as_tensor(model_params[6]).detach().to(torch.float32)
    logits = torch.as_tensor(model_params[7]).detach().to(torch.float32)
    codebooks = torch.as_tensor(model_params[8]).detach().to(torch.float32)

    _, k, d = codebooks.shape
    if k != 64 or d != 512:
        raise ValueError(f"当前 checkpoint codebook 维度不是 [L,64,512]：{codebooks.shape}")
    if codebooks.shape[0] != 1:
        raise ValueError(
            f"当前 checkpoint 的 codebook 有 {codebooks.shape[0]} 个 level；本导出格式要求单 level（64*512）。"
        )

    weights64 = _compute_weights_64(logits, topk=int(topk), require_single_level=True).cpu().numpy()
    codebook = codebooks[0].cpu().numpy()

    lvl_dir = out_root / f"L{int(level)}"
    ply_out = lvl_dir / "gaussians_with_weights64.ply"
    bin_out = lvl_dir / "codebook_64x512.bin"

    extra = {f"weight_{i}": weights64[:, i] for i in range(64)}
    _write_gaussian_ply_with_extra_from_tensors(
        xyz=xyz_t,
        features_dc=f_dc_t,
        features_rest=f_rest_t,
        opacity=opacity_t,
        scaling=scaling_t,
        rotation=rotation_t,
        extra_f4=extra,
        out_path=ply_out,
        text=False,
    )
    _write_codebook_bin(codebook, bin_out)

    print(f"[OK] level={level}")
    print(f"  ckpt: {ckpt_path}")
    print(f"  ply:  {ply_out}   (P={int(xyz_t.shape[0])}, sh_degree={active_sh_degree})")
    print(f"  bin:  {bin_out}   (len={64 * 512})")


@dataclass(frozen=True)
class ExportJob:
    output_dir: Path
    checkpoint: int
    levels: tuple[int, ...]
    queries: tuple[str, ...] = ()
    topk: int = 4
    model_root: Path | None = None
    ckpt_root: Path | None = None
    ckpt_prefix: str | None = None
    scene_id: str | None = None
    device: torch.device | None = None


def export_final_products(job: ExportJob) -> Path:
    if job.model_root is not None:
        out_root = job.output_dir / f"chkpnt{int(job.checkpoint)}"
    else:
        if job.ckpt_root is None or job.ckpt_prefix is None:
            raise ValueError("必须提供 model_root，或同时提供 ckpt_root 与 ckpt_prefix")
        scene_id = job.scene_id or _infer_scene_id_from_ckpt_prefix(job.ckpt_prefix)
        out_root = job.output_dir / scene_id / f"chkpnt{int(job.checkpoint)}"

    out_root.mkdir(parents=True, exist_ok=True)

    device = job.device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    queries_out = out_root / "queries.json"
    _write_queries_json(list(job.queries), queries_out, device=device)

    for level in job.levels:
        if job.model_root is not None:
            ckpt_dir = _resolve_level_model_dir(job.model_root, int(level))
        else:
            ckpt_dir = _resolve_ckpt_dir(str(job.ckpt_root), str(job.ckpt_prefix), level=int(level))
        ckpt_path = ckpt_dir / f"chkpnt{int(job.checkpoint)}.pth"
        _export_level_checkpoint(ckpt_path=ckpt_path, level=int(level), out_root=out_root, topk=job.topk)

    print(f"[DONE] outputs in: {out_root}")
    return out_root


def main():
    parser = ArgumentParser(description="Export LangSplatV2 final products (PLY + codebook.bin + queries.json)")

    parser.add_argument(
        "--model_root",
        type=str,
        default=None,
        help="job 模式：训练 model_path 基路径（不含 _level 后缀），如 /job/langsplatv2",
    )
    parser.add_argument("--scene_id", type=str, default=None, help="legacy 模式输出子目录名")
    parser.add_argument("--ckpt_root", type=str, default=None)
    parser.add_argument("--ckpt_prefix", type=str, default=None)
    parser.add_argument("--checkpoint", type=int, required=True)
    parser.add_argument("--topk", type=int, default=4, help="导出 weights 时的 top-k 稀疏化（0/>=64 表示不稀疏）")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--feature_level", type=int, default=1, help="legacy 单 level 导出（默认 1）")
    parser.add_argument("--levels", type=int, nargs="+", default=None, help="导出多个 level，如 --levels 1 2 3")
    parser.add_argument("--queries", type=str, nargs="*", default=(), help="query 文本列表；留空则跳过 queries.json")
    parser.add_argument("--device", type=str, default=None, choices=["cuda", "cpu"])

    args = parser.parse_args()
    levels = [int(x) for x in args.levels] if args.levels else [int(args.feature_level)]
    device = torch.device(args.device if args.device is not None else ("cuda" if torch.cuda.is_available() else "cpu"))

    if args.model_root:
        job = ExportJob(
            model_root=Path(args.model_root),
            output_dir=Path(args.output_dir),
            checkpoint=int(args.checkpoint),
            levels=tuple(levels),
            queries=tuple(args.queries or ()),
            topk=int(args.topk),
            device=device,
        )
    else:
        if not args.ckpt_root or not args.ckpt_prefix:
            parser.error("请提供 --model_root，或同时提供 --ckpt_root 与 --ckpt_prefix")
        job = ExportJob(
            ckpt_root=Path(args.ckpt_root),
            ckpt_prefix=str(args.ckpt_prefix),
            scene_id=args.scene_id,
            output_dir=Path(args.output_dir),
            checkpoint=int(args.checkpoint),
            levels=tuple(levels),
            queries=tuple(args.queries or ()),
            topk=int(args.topk),
            device=device,
        )

    export_final_products(job)


if __name__ == "__main__":
    main()
