from __future__ import annotations

from pathlib import Path

from ..domain.input_modes import get_iteration, is_native_3dgs_ply_mode
from ..domain.jobs import JobSpec
from ..jobs.image_canvas import unify_image_canvases
from ..jobs.image_names import ascii_image_filenames
from ..jobs.paths import JobPaths
from ..jobs.ply_validation import validate_native_3dgs_ply


def ingest_job_files(
    spec: JobSpec,
    files: list[tuple[str, bytes]],
    paths: JobPaths,
    output_relative: str,
) -> None:
    if is_native_3dgs_ply_mode(spec):
        _ingest_native_3dgs_ply(spec, files, paths, output_relative)
        return
    _ingest_images(files, paths)


def _ingest_images(files: list[tuple[str, bytes]], paths: JobPaths) -> None:
    if not files:
        raise ValueError("请至少上传一张图片")
    from ..jobs.storage import save_upload_files

    unified = ascii_image_filenames(unify_image_canvases(files))
    saved = save_upload_files(unified, paths.input_dir)
    if saved == 0:
        raise ValueError("未检测到有效文件名")


def _ingest_native_3dgs_ply(
    spec: JobSpec,
    files: list[tuple[str, bytes]],
    paths: JobPaths,
    output_relative: str,
) -> None:
    if len(files) != 1:
        raise ValueError("native_3dgs_ply 模式需上传一个 point_cloud.ply 文件")
    filename, content = files[0]
    if Path(filename).suffix.lower() != ".ply":
        raise ValueError("native_3dgs_ply 模式仅接受 .ply 文件")
    validate_native_3dgs_ply(content)

    iteration = get_iteration(spec)
    ply_path = paths.gs_output_ply(output_relative, iteration)
    ply_path.parent.mkdir(parents=True, exist_ok=True)
    ply_path.write_bytes(content)
    _write_cfg_args(paths, output_relative, iteration)


def _write_cfg_args(paths: JobPaths, output_relative: str, iteration: int) -> None:
    output_dir = paths.output_dir(output_relative)
    source_path = paths.colmap_dir
    cfg_path = output_dir / "cfg_args"
    cfg_content = (
        "Namespace("
        f"source_path='{source_path}', "
        f"model_path='{output_dir}', "
        "images='images', "
        "resolution=-1, "
        "white_background=False, "
        "data_device='cpu', "
        "eval=False, "
        "llff=8, "
        "kernel_size=0.0, "
        "use_unbounded_opacity=False, "
        "sh_degree=3"
        ")"
    )
    cfg_path.write_text(cfg_content, encoding="utf-8")
