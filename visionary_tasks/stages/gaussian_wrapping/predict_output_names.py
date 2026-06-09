from __future__ import annotations

import os
from dataclasses import dataclass

from ...settings.gaussian_wrapping import GaussianWrappingJobConfig


@dataclass(frozen=True)
class PredictedOutputs:
    mesh_ply: str
    mesh_textured_ply: str | None


def _iso_suffix(config: GaussianWrappingJobConfig) -> str:
    ext = config.extraction
    if ext.sdf_mode == "exact_computation":
        transmittance_threshold = 0.5 + ext.isosurface_value
        if transmittance_threshold != 0.5:
            return f"_transmittance_threshold_{transmittance_threshold}"
        return ""
    if ext.isosurface_value != 0:
        return f"_iso_{ext.isosurface_value}"
    return ""


def _geometry_mesh_basename(config: GaussianWrappingJobConfig) -> str:
    ext = config.extraction
    if ext.mesh:
        return os.path.basename(ext.mesh)

    name = f"mesh_{ext.sdf_mode}_{ext.n_pivots}pivots{_iso_suffix(config)}.ply"
    if ext.postprocess:
        name = name.replace(".ply", "_post.ply")
    if config.decimation.apply_decimation:
        name = name.replace(".ply", "_decimated_with_blender.ply")
    return name


def predict_output_names(config: GaussianWrappingJobConfig) -> PredictedOutputs:
    mesh_ply = _geometry_mesh_basename(config)
    if not config.texture_enabled:
        return PredictedOutputs(mesh_ply=mesh_ply, mesh_textured_ply=None)

    stem, ext = os.path.splitext(mesh_ply)
    last_iter = config.texture.texture_n_iter - 1
    mesh_textured_ply = f"{stem}_texture_refined_{last_iter}{ext}"
    return PredictedOutputs(mesh_ply=mesh_ply, mesh_textured_ply=mesh_textured_ply)
