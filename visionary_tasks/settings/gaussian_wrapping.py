from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EXTRACT_SCRIPT = "gaussian_wrapping/scripts/extract_and_texture_from_native_3dgs.py"

_LEGACY_EXTRACTION_KEYS = frozenset({"iteration", "resolution"})


@dataclass
class GaussianWrappingExtractionConfig:
    rasterizer: str = "ours"
    sdf_mode: str = "ours"
    n_pivots: int = 2
    n_binary_steps: int = 10
    isosurface_value: float = 0.0
    dtype: str = "int32"
    use_valid_mask: bool = True
    postprocess: bool = True
    filter_large_edges: bool = True
    mesh: str | None = None


@dataclass
class GaussianWrappingTextureConfig:
    texture_n_iter: int = 1000
    texture_lr: float = 0.0025
    texture_lambda_dssim: float = 0.2
    texture_sh_degree: int = 0


@dataclass
class GaussianWrappingDecimationConfig:
    apply_decimation: bool = False
    decimate_ratio: float = 0.3


@dataclass
class GaussianWrappingOutputsConfig:
    mesh_ply_names: list[str] = field(default_factory=lambda: ["mesh_ours_2pivots_post.ply"])
    mesh_textured_ply_names: list[str] = field(
        default_factory=lambda: ["mesh_ours_2pivots_post_texture_refined_999.ply"]
    )


@dataclass
class GaussianWrappingJobConfig:
    worker_image: str
    extraction: GaussianWrappingExtractionConfig
    texture: GaussianWrappingTextureConfig
    decimation: GaussianWrappingDecimationConfig
    outputs: GaussianWrappingOutputsConfig
    texture_enabled: bool = True

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "GaussianWrappingJobConfig":
        outputs_payload = dict(payload.get("outputs") or {})
        extraction_payload = {
            key: value
            for key, value in dict(payload.get("extraction") or {}).items()
            if key not in _LEGACY_EXTRACTION_KEYS
        }
        return cls(
            worker_image=str(payload.get("worker_image", "gaussian-wrapping:latest")),
            extraction=GaussianWrappingExtractionConfig(**extraction_payload),
            texture=GaussianWrappingTextureConfig(**dict(payload.get("texture") or {})),
            decimation=GaussianWrappingDecimationConfig(**dict(payload.get("decimation") or {})),
            outputs=GaussianWrappingOutputsConfig(
                mesh_ply_names=list(outputs_payload.get("mesh_ply_names") or ["mesh_ours_2pivots_post.ply"]),
                mesh_textured_ply_names=list(
                    outputs_payload.get("mesh_textured_ply_names")
                    or ["mesh_ours_2pivots_post_texture_refined_999.ply"]
                ),
            ),
            texture_enabled=bool(payload.get("texture_enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_image": self.worker_image,
            "extraction": asdict(self.extraction),
            "texture": asdict(self.texture),
            "decimation": asdict(self.decimation),
            "outputs": asdict(self.outputs),
            "texture_enabled": self.texture_enabled,
        }
