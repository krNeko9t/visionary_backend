from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

JobStatus = Literal["queued", "running", "done", "error", "cancelled"]
StageStatus = Literal["pending", "running", "done", "error", "skipped", "cancelled"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobSpec:
    outputs: list[str]
    options: dict[str, Any] = field(default_factory=dict)
    advanced: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "outputs": list(self.outputs),
            "options": dict(self.options),
        }
        if self.advanced is not None:
            payload["advanced"] = dict(self.advanced)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobSpec:
        outputs = data.get("outputs") or []
        if not isinstance(outputs, list):
            raise ValueError("spec.outputs 必须是列表")
        return cls(
            outputs=[str(item) for item in outputs],
            options=dict(data.get("options") or {}),
            advanced=dict(data["advanced"]) if data.get("advanced") else None,
        )


@dataclass
class Artifact:
    id: str
    stage_id: str
    type: str
    path: str
    mime: str | None = None
    downloadable: bool = True
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage_id": self.stage_id,
            "type": self.type,
            "path": self.path,
            "mime": self.mime,
            "downloadable": self.downloadable,
            "label": self.label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        return cls(
            id=str(data["id"]),
            stage_id=str(data["stage_id"]),
            type=str(data["type"]),
            path=str(data["path"]),
            mime=data.get("mime"),
            downloadable=bool(data.get("downloadable", True)),
            label=data.get("label"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class ProgressEvent:
    stage_id: str
    event_type: str
    progress: float | None = None
    iteration: int | None = None
    total_iterations: int | None = None
    message: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "event_type": self.event_type,
            "progress": self.progress,
            "iteration": self.iteration,
            "total_iterations": self.total_iterations,
            "message": self.message,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProgressEvent:
        return cls(
            stage_id=str(data["stage_id"]),
            event_type=str(data["event_type"]),
            progress=data.get("progress"),
            iteration=data.get("iteration"),
            total_iterations=data.get("total_iterations"),
            message=data.get("message"),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass
class StageState:
    stage_id: str
    status: StageStatus
    started_at: str | None = None
    ended_at: str | None = None
    progress: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "progress": self.progress,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageState:
        return cls(
            stage_id=str(data["stage_id"]),
            status=str(data["status"]),  # type: ignore[arg-type]
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            progress=float(data.get("progress", 0.0)),
            error=data.get("error"),
        )

    @classmethod
    def pending(cls, stage_id: str) -> StageState:
        return cls(stage_id=stage_id, status="pending")


@dataclass
class JobState:
    job_id: str
    spec: JobSpec
    status: JobStatus
    stages: list[StageState]
    artifacts: list[Artifact]
    created_at: str
    updated_at: str
    progress: float = 0.0
    current_stage_id: str | None = None
    error: str | None = None
    cancel_requested: bool = False
    planned_stages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "spec": self.spec.to_dict(),
            "status": self.status,
            "stages": [stage.to_dict() for stage in self.stages],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress": self.progress,
            "current_stage_id": self.current_stage_id,
            "error": self.error,
            "cancel_requested": self.cancel_requested,
            "planned_stages": list(self.planned_stages),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobState:
        return cls(
            job_id=str(data["job_id"]),
            spec=JobSpec.from_dict(data["spec"]),
            status=str(data["status"]),  # type: ignore[arg-type]
            stages=[StageState.from_dict(item) for item in data.get("stages") or []],
            artifacts=[Artifact.from_dict(item) for item in data.get("artifacts") or []],
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            progress=float(data.get("progress", 0.0)),
            current_stage_id=data.get("current_stage_id"),
            error=data.get("error"),
            cancel_requested=bool(data.get("cancel_requested", False)),
            planned_stages=[str(item) for item in data.get("planned_stages") or []],
        )

    def artifact_by_id(self, artifact_id: str) -> Artifact | None:
        for artifact in self.artifacts:
            if artifact.id == artifact_id:
                return artifact
        return None
