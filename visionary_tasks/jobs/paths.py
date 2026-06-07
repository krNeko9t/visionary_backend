from dataclasses import dataclass
from pathlib import Path

from ..settings import Settings

STATUS_FILENAME = "progress.json"


def _first_existing(candidates) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    root: Path

    @classmethod
    def from_settings(cls, settings: Settings, job_id: str) -> "JobPaths":
        return cls(job_id=job_id, root=settings.jobs_root / job_id)

    @property
    def status_file(self) -> Path:
        return self.root / STATUS_FILENAME

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def colmap_dir(self) -> Path:
        return self.root / "colmap"

    def output_dir(self, output_relative: str = "output") -> Path:
        return self.root / output_relative

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    def stage_artifact_file(self, stage_name: str, filename: str = "result.json") -> Path:
        return self.artifacts_dir / stage_name / filename

    def artifact(self, relative: str) -> Path:
        return self.root / relative

    def gs_config_path(self) -> Path:
        return self.root / "config" / "3dgs.yaml"

    def colmap_config_path(self) -> Path:
        return self.root / "config" / "colmap.yaml"

    def langsplat_config_path(self) -> Path:
        return self.root / "config" / "langsplat.yaml"

    def gaussian_wrapping_config_path(self) -> Path:
        return self.root / "config" / "gaussian-wrapping.yaml"

    def gs_output_ply(self, output_relative: str, output_iteration: int) -> Path:
        return (
            self.output_dir(output_relative)
            / f"point_cloud/iteration_{output_iteration}/point_cloud.ply"
        )

    def gs_checkpoint(self, output_relative: str, output_iteration: int) -> Path:
        return self.output_dir(output_relative) / f"chkpnt{output_iteration}.pth"

    def langsplat_model_dir(self, model_relative: str) -> Path:
        return self.root / model_relative

    def wrapping_mesh_ply(
        self,
        output_relative: str,
        mesh_ply_names: tuple[str, ...],
    ) -> Path | None:
        return _first_existing(
            self.output_dir(output_relative) / name
            for name in mesh_ply_names
        )

    def wrapping_mesh_textured_ply(
        self,
        output_relative: str,
        mesh_textured_ply_names: tuple[str, ...],
    ) -> Path | None:
        return _first_existing(
            self.output_dir(output_relative) / name
            for name in mesh_textured_ply_names
        )

    def ensure_dirs(self, output_relative: str = "output") -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.colmap_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir(output_relative).mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
