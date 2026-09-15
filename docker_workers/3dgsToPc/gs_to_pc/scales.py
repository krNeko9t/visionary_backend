"""Normalize Gaussian scale dimensions for 3D covariance construction."""

from __future__ import annotations

import numpy as np

# 2DGS 只有平面内两个 log-scale。补一个更薄的第三轴，使 3D 协方差变成扁平椭球，
# Poisson 重建才能把它当曲面采样。e^{-4} ≈ 0.018，约为较小平面尺度的 1/55。
_2DGS_THIN_AXIS_LOG_OFFSET = 4.0


def ensure_3d_scales(scales: np.ndarray) -> np.ndarray:
    if scales.ndim != 2:
        raise ValueError(f"scale 数组维度无效: {scales.shape}")
    n_scales = scales.shape[1]
    if n_scales == 3:
        return scales
    if n_scales == 2:
        thin = scales.min(axis=1, keepdims=True) - _2DGS_THIN_AXIS_LOG_OFFSET
        return np.concatenate([scales, thin], axis=1)
    raise ValueError(
        f"PLY 的 scale_* 数量必须是 2（2DGS）或 3（3DGS），当前为 {n_scales}"
    )
