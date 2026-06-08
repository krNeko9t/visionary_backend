from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ...domain.jobs import Artifact, JobSpec, JobState, ProgressEvent, StageState

JobStatus = Literal["queued", "running", "done", "error", "cancelled"]
StageStatus = Literal["pending", "running", "done", "error", "skipped", "cancelled"]


class JobSpecRequest(BaseModel):
    outputs: list[str] = Field(min_length=1)
    preset: str = "standard"
    options: dict[str, Any] = Field(default_factory=dict)
    advanced: dict[str, Any] | None = None

    def to_domain(self) -> JobSpec:
        return JobSpec(
            outputs=list(self.outputs),
            preset=self.preset,
            options=dict(self.options),
            advanced=dict(self.advanced) if self.advanced else None,
        )


class ArtifactItem(BaseModel):
    id: str
    stage_id: str
    type: str
    path: str
    mime: str | None = None
    downloadable: bool = True
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, artifact: Artifact) -> ArtifactItem:
        return cls(**artifact.to_dict())


class StageStatusItem(BaseModel):
    stage_id: str
    status: StageStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    progress: float = 0.0
    error: str | None = None

    @classmethod
    def from_domain(cls, stage: StageState) -> StageStatusItem:
        return cls(
            stage_id=stage.stage_id,
            status=stage.status,
            started_at=datetime.fromisoformat(stage.started_at) if stage.started_at else None,
            ended_at=datetime.fromisoformat(stage.ended_at) if stage.ended_at else None,
            progress=stage.progress,
            error=stage.error,
        )


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    outputs: list[str]
    planned_stages: list[str]


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    progress: float = Field(ge=0.0, le=100.0)
    created_at: datetime
    updated_at: datetime
    current_stage_id: str | None = None
    error: str | None = None
    outputs: list[str]
    planned_stages: list[str] = Field(default_factory=list)
    stages: list[StageStatusItem] = Field(default_factory=list)
    artifacts: list[ArtifactItem] = Field(default_factory=list)

    @classmethod
    def from_state(cls, state: JobState) -> JobStatusResponse:
        return cls(
            job_id=state.job_id,
            status=state.status,
            message=_derive_message(state),
            progress=state.progress,
            created_at=datetime.fromisoformat(state.created_at),
            updated_at=datetime.fromisoformat(state.updated_at),
            current_stage_id=state.current_stage_id,
            error=state.error,
            outputs=list(state.spec.outputs),
            planned_stages=list(state.planned_stages),
            stages=[StageStatusItem.from_domain(stage) for stage in state.stages],
            artifacts=[ArtifactItem.from_domain(artifact) for artifact in state.artifacts],
        )


class ArtifactListResponse(BaseModel):
    job_id: str
    artifacts: list[ArtifactItem]


class ProgressEventItem(BaseModel):
    stage_id: str
    event_type: str
    progress: float | None = None
    iteration: int | None = None
    total_iterations: int | None = None
    message: str | None = None
    timestamp: datetime

    @classmethod
    def from_domain(cls, event: ProgressEvent) -> ProgressEventItem:
        return cls(
            stage_id=event.stage_id,
            event_type=event.event_type,
            progress=event.progress,
            iteration=event.iteration,
            total_iterations=event.total_iterations,
            message=event.message,
            timestamp=datetime.fromisoformat(event.timestamp) if event.timestamp else datetime.now(),
        )


class EventListResponse(BaseModel):
    job_id: str
    events: list[ProgressEventItem]


class CapabilitiesResponse(BaseModel):
    input_modes: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]]
    presets: list[dict[str, Any]]
    stages: list[dict[str, Any]]


class CancelJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


def _derive_message(state: JobState) -> str:
    if state.status == "queued":
        return "任务排队中"
    if state.status == "running":
        return f"{state.current_stage_id} 执行中" if state.current_stage_id else "任务执行中"
    if state.status == "done":
        return "任务完成"
    if state.status == "cancelled":
        return "任务已取消"
    return state.error or "任务失败"
