from __future__ import annotations

from pathlib import Path

import numpy as np
import torch


def load_compact_language_maps(language_feature_dir: str, image_name: str) -> tuple[torch.Tensor, torch.Tensor]:
    stem = Path(language_feature_dir) / image_name
    seg_map = torch.from_numpy(np.load(str(stem) + "_s.npy"))
    feature_map = torch.from_numpy(np.load(str(stem) + "_f.npy"))
    if seg_map.ndim != 3:
        raise ValueError(f"expected seg map (L,H,W), got {tuple(seg_map.shape)}")
    if feature_map.ndim != 2:
        raise ValueError(f"expected feature map (K,C), got {tuple(feature_map.shape)}")
    return seg_map, feature_map


def decode_dense_language_feature(
    seg_map: torch.Tensor,
    feature_map: torch.Tensor,
    feature_level: int,
    device: torch.device | str,
) -> tuple[torch.Tensor, torch.Tensor]:
    if feature_level < 0 or feature_level >= seg_map.shape[0]:
        raise ValueError(f"feature_level={feature_level}")

    index = seg_map[feature_level].to(device=device, dtype=torch.long)
    mask = (index != -1).unsqueeze(0)
    dense = feature_map.to(device=device, dtype=torch.float32)[index.clamp(min=0)]
    return dense.permute(2, 0, 1).contiguous(), mask
