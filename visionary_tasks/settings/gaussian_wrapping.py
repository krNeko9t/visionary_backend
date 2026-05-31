from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

from .cli import format_cli_arg, format_negatable_bool

SCRIPT = "gaussian_wrapping/scripts/extract_and_texture_from_native_3dgs.py"


def _parse_csv_names(raw: str, default: tuple[str, ...]) -> tuple[str, ...]:
    names = tuple(item.strip() for item in raw.split(",") if item.strip())
    return names or default


@dataclass(frozen=True)
class GaussianWrappingSettings:
    worker_image: str

    @classmethod
    def from_env(cls) -> "GaussianWrappingSettings":
        return cls(
            worker_image=os.getenv("WRAPPING_WORKER_IMAGE", "gaussian-wrapping"),
        )


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
    extraction: GaussianWrappingExtractionConfig
    texture: GaussianWrappingTextureConfig
    decimation: GaussianWrappingDecimationConfig
    outputs: GaussianWrappingOutputsConfig

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "GaussianWrappingJobConfig":
        outputs_payload = dict(payload.get("outputs") or {})
        return cls(
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
        )

    def sync_gs_iteration(self, output_iteration: int) -> "GaussianWrappingJobConfig":
        self.extraction.iteration = output_iteration
        return self

    def apply_env_overrides(self) -> "GaussianWrappingJobConfig":
        if os.getenv("WRAPPING_PIVOTS") is not None:
            self.extraction.n_pivots = int(os.getenv("WRAPPING_PIVOTS", "2"))
        if os.getenv("WRAPPING_ITERATION") is not None:
            self.extraction.iteration = int(os.getenv("WRAPPING_ITERATION", "500"))
        if os.getenv("WRAPPING_SDF_MODE") is not None:
            self.extraction.sdf_mode = os.getenv("WRAPPING_SDF_MODE", "ours")
        if os.getenv("WRAPPING_RASTERIZER") is not None:
            self.extraction.rasterizer = os.getenv("WRAPPING_RASTERIZER", "ours")
        mesh_names = os.getenv("WRAPPING_MESH_PLY_NAMES")
        if mesh_names is not None:
            self.outputs.mesh_ply_names = list(
                _parse_csv_names(mesh_names, tuple(self.outputs.mesh_ply_names))
            )
        textured_names = os.getenv("WRAPPING_MESH_TEXTURED_PLY_NAMES")
        if textured_names is not None:
            self.outputs.mesh_textured_ply_names = list(
                _parse_csv_names(textured_names, tuple(self.outputs.mesh_textured_ply_names))
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "extraction": asdict(self.extraction),
            "texture": asdict(self.texture),
            "decimation": asdict(self.decimation),
            "outputs": asdict(self.outputs),
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
        return command
