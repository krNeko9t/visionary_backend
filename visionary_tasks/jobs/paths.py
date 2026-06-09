from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..settings import Settings


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
    def from_settings(cls, settings: Settings, job_id: str) -> JobPaths:
        return cls(job_id=job_id, root=settings.jobs_root / job_id)

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def job_state_file(self) -> Path:
        return self.state_dir / "job.json"

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    def stage_dir(self, stage_id: str) -> Path:
        return self.root / "stages" / stage_id

    def stage_result_file(self, stage_id: str) -> Path:
        return self.stage_dir(stage_id) / "result.json"

    def stage_events_file(self, stage_id: str) -> Path:
        return self.events_dir / f"{stage_id}.jsonl"

    def stage_config_path(self, stage_id: str) -> Path:
        filename = {
            "3dgs": "3dgs.yaml",
            "gw-train": "gw-train.yaml",
            "colmap": "colmap.yaml",
            "langsplat": "langsplat.yaml",
            "gaussian-wrapping": "gaussian-wrapping.yaml",
            "3dgs-to-pc": "3dgs-to-pc.yaml",
        }[stage_id]
        return self.config_dir / filename

    def resolve(self, relative: str) -> Path:
        return self.root / relative

    @property
    def colmap_dir(self) -> Path:
        return self.root / "colmap"

    def output_dir(self, output_relative: str = "output") -> Path:
        return self.root / output_relative

    def gs_output_ply(self, output_relative: str, output_iteration: int) -> Path:
        return (
            self.output_dir(output_relative)
            / f"point_cloud/iteration_{output_iteration}/point_cloud.ply"
        )

    def gs_checkpoint(self, output_relative: str, output_iteration: int) -> Path:
        return self.output_dir(output_relative) / f"chkpnt{output_iteration}.pth"

    def langsplat_model_dir(self, model_relative: str, feature_level: int) -> Path:
        return self.root / f"{model_relative}_{feature_level}"

    def langsplat_export_dir(self, output_relative: str) -> Path:
        return self.root / output_relative

    def langsplat_export_root(self, output_relative: str, checkpoint: int) -> Path:
        return self.langsplat_export_dir(output_relative) / f"chkpnt{checkpoint}"

    def wrapping_mesh_ply(
        self,
        output_relative: str,
        mesh_ply_names: tuple[str, ...],
    ) -> Path | None:
        return _first_existing(self.output_dir(output_relative) / name for name in mesh_ply_names)

    def wrapping_mesh_textured_ply(
        self,
        output_relative: str,
        mesh_textured_ply_names: tuple[str, ...],
    ) -> Path | None:
        return _first_existing(
            self.output_dir(output_relative) / name for name in mesh_textured_ply_names
        )

    def mesh_poisson_ply(
        self,
        output_relative: str,
        mesh_ply_names: tuple[str, ...],
    ) -> Path | None:
        return _first_existing(self.output_dir(output_relative) / name for name in mesh_ply_names)

    def ensure_layout(self, output_relative: str = "output") -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.colmap_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir(output_relative).mkdir(parents=True, exist_ok=True)
        (self.root / "stages").mkdir(parents=True, exist_ok=True)
