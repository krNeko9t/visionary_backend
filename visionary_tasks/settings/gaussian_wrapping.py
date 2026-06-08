from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .cli import format_cli_arg, format_negatable_bool

SCRIPT = "gaussian_wrapping/scripts/extract_and_texture_from_native_3dgs.py"


@dataclass
class GaussianWrappingExtractionConfig:
    iteration: int = 500
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
    resolution: int = -1


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
        return cls(
            worker_image=str(payload.get("worker_image", "gaussian-wrapping:latest")),
            extraction=GaussianWrappingExtractionConfig(**dict(payload.get("extraction") or {})),
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

    def sync_gs_iteration(self, output_iteration: int) -> "GaussianWrappingJobConfig":
        self.extraction.iteration = output_iteration
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_image": self.worker_image,
            "extraction": asdict(self.extraction),
            "texture": asdict(self.texture),
            "decimation": asdict(self.decimation),
            "outputs": asdict(self.outputs),
            "texture_enabled": self.texture_enabled,
        }

    def to_container_command(self, source_path: str, model_path: str) -> list[str]:
        command = ["python", SCRIPT, "-s", source_path, "-m", model_path]
        ext = self.extraction
        command.extend(
            [
                "--iteration",
                str(ext.iteration),
                "--rasterizer",
                ext.rasterizer,
                "--sdf_mode",
                ext.sdf_mode,
                "--n_pivots",
                str(ext.n_pivots),
                "--n_binary_steps",
                str(ext.n_binary_steps),
                "--isosurface_value",
                str(ext.isosurface_value),
                "--dtype",
                ext.dtype,
            ]
        )
        if ext.resolution >= 0:
            command.extend(["-r", str(ext.resolution)])
        command.extend(format_negatable_bool("use_valid_mask", ext.use_valid_mask))
        command.extend(format_negatable_bool("postprocess", ext.postprocess))
        command.extend(format_negatable_bool("filter_large_edges", ext.filter_large_edges))
        if ext.mesh:
            command.extend(["--mesh", ext.mesh])
        command.extend(format_cli_arg("texture_n_iter", self.texture.texture_n_iter))
        command.extend(format_cli_arg("texture_lr", self.texture.texture_lr))
        command.extend(format_cli_arg("texture_lambda_dssim", self.texture.texture_lambda_dssim))
        command.extend(format_cli_arg("texture_sh_degree", self.texture.texture_sh_degree))
        if self.decimation.apply_decimation:
            command.append("--apply_decimation")
            command.extend(format_cli_arg("decimate_ratio", self.decimation.decimate_ratio))
        if not self.texture_enabled:
            command.append("--extraction_only")
        return command
