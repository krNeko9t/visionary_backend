import os
from dataclasses import dataclass

SCRIPT = "gaussian_wrapping/scripts/extract_and_texture_from_native_3dgs.py"


def _parse_csv_names(raw: str, default: tuple[str, ...]) -> tuple[str, ...]:
    names = tuple(item.strip() for item in raw.split(",") if item.strip())
    return names or default


@dataclass(frozen=True)
class GaussianWrappingSettings:
    worker_image: str
    pivots: int
    iteration: int
    sdf_mode: str
    rasterizer: str
    mesh_ply_names: tuple[str, ...]
    mesh_textured_ply_names: tuple[str, ...]

    @classmethod
    def from_env(cls, gs_save_iteration: int) -> "GaussianWrappingSettings":
        return cls(
            worker_image=os.getenv("WRAPPING_WORKER_IMAGE", "gaussian-wrapping"),
            pivots=int(os.getenv("WRAPPING_PIVOTS", "2")),
            iteration=int(os.getenv("WRAPPING_ITERATION", str(gs_save_iteration))),
            sdf_mode=os.getenv("WRAPPING_SDF_MODE", "ours"),
            rasterizer=os.getenv("WRAPPING_RASTERIZER", "ours"),
            mesh_ply_names=_parse_csv_names(
                os.getenv("WRAPPING_MESH_PLY_NAMES", ""),
                ("mesh_ours_2pivots_post.ply",),
            ),
            mesh_textured_ply_names=_parse_csv_names(
                os.getenv("WRAPPING_MESH_TEXTURED_PLY_NAMES", ""),
                ("mesh_ours_2pivots_post_texture_refined_999.ply",),
            ),
        )

    def container_command(self, source_path: str, model_path: str) -> list[str]:
        return [
            "python",
            SCRIPT,
            "-s",
            source_path,
            "-m",
            model_path,
            "--iteration",
            str(self.iteration),
            "--rasterizer",
            self.rasterizer,
            "--sdf_mode",
            self.sdf_mode,
            "-r",
            str(self.pivots),
        ]
