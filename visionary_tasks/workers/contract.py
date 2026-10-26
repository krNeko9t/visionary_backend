from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from visionary_progress import make_progress_event

from ..domain.jobs import Artifact

WorkerStatus = Literal["done", "error"]


@dataclass
class WorkerInput:
    job_id: str
    job_root: Path
    stage_id: str
    stage_dir: Path
    config_path: Path


@dataclass
class WorkerResult:
    stage_id: str
    status: WorkerStatus
    artifacts: list[Artifact] = field(default_factory=list)
    error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    logs: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "status": self.status,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "error": self.error,
            "metrics": dict(self.metrics),
            "logs": self.logs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerResult:
        return cls(
            stage_id=str(data["stage_id"]),
            status=str(data["status"]),  # type: ignore[arg-type]
            artifacts=[Artifact.from_dict(item) for item in data.get("artifacts") or []],
            error=data.get("error"),
            metrics=dict(data.get("metrics") or {}),
            logs=data.get("logs"),
        )
