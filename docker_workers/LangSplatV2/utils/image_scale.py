"""LangSplat 图像缩放。

resolution=-1 表示长边上限 AUTO_MAX_SIDE（1024），与论文常用 1K 输入对齐。
当前这台 4090（24GB）上，语言特征 loss 会物化 512×H×W：
1024×768 ≈ 1.6GB/图；若按高边 1080 缩放横图，会变成 1439×1080 ≈ 3.2GB/图，
再叠加反传和全部相机 RGB，会把显存顶满并拖垮分配器。
"""

from __future__ import annotations

AUTO_MAX_SIDE = 1024
_DOWNSCALE_WARNED = False


def scaled_resolution(
    orig_w: int,
    orig_h: int,
    resolution: int,
    resolution_scale: float = 1.0,
) -> tuple[int, int]:
    if orig_w <= 0 or orig_h <= 0:
        raise ValueError(f"invalid image size: {orig_w}x{orig_h}")

    if resolution in (1, 2, 4, 8):
        scale = float(resolution_scale) * float(resolution)
        return round(orig_w / scale), round(orig_h / scale)

    if resolution == -1:
        long_side = max(orig_w, orig_h)
        global_down = long_side / AUTO_MAX_SIDE if long_side > AUTO_MAX_SIDE else 1.0
        _warn_auto_downscale(orig_w, orig_h, long_side)
    else:
        global_down = orig_w / float(resolution)

    scale = float(global_down) * float(resolution_scale)
    return int(orig_w / scale), int(orig_h / scale)


def _warn_auto_downscale(orig_w: int, orig_h: int, long_side: int) -> None:
    global _DOWNSCALE_WARNED
    if long_side <= AUTO_MAX_SIDE or _DOWNSCALE_WARNED:
        return
    print(
        f"[ INFO ] Input {orig_w}x{orig_h} exceeds LangSplat 1K cap; "
        f"scaling so the long side is {AUTO_MAX_SIDE}. "
        "Pass --resolution/-r 1 to keep the original size."
    )
    _DOWNSCALE_WARNED = True
