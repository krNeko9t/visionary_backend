from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..domain.jobs import Artifact, ProgressEvent, now_iso

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


def make_progress_event(
    stage_id: str,
    *,
    event_type: str = "progress",
    progress: float | None = None,
    iteration: int | None = None,
    total_iterations: int | None = None,
    message: str | None = None,
) -> ProgressEvent:
    return ProgressEvent(
        stage_id=stage_id,
        event_type=event_type,
        progress=progress,
        iteration=iteration,
        total_iterations=total_iterations,
        message=message,
        timestamp=now_iso(),
    )
