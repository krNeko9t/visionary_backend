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

    def output_dir(self, settings: Settings) -> Path:
        return self.root / settings.gs_output_relative

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    def stage_artifact_file(self, stage_name: str, filename: str = "result.json") -> Path:
        return self.artifacts_dir / stage_name / filename

    def artifact(self, relative: str) -> Path:
        return self.root / relative

    def gs_config_path(self) -> Path:
        return self.root / "config" / "3dgs.yaml"

    def gs_output_ply(self, settings: Settings, output_iteration: int) -> Path:
        return (
            self.output_dir(settings)
            / f"point_cloud/iteration_{output_iteration}/point_cloud.ply"
        )

    def gs_checkpoint(self, settings: Settings, output_iteration: int) -> Path:
        return self.output_dir(settings) / f"chkpnt{output_iteration}.pth"

    def langsplat_model_dir(self, settings: Settings) -> Path:
        return self.root / settings.langsplat.model_relative

    def wrapping_mesh_ply(self, settings: Settings) -> Path | None:
        return _first_existing(
            self.output_dir(settings) / name
            for name in settings.wrapping.mesh_ply_names
        )

    def wrapping_mesh_textured_ply(self, settings: Settings) -> Path | None:
        return _first_existing(
            self.output_dir(settings) / name
            for name in settings.wrapping.mesh_textured_ply_names
        )

    def ensure_dirs(self, settings: Settings) -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.colmap_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir(settings).mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
