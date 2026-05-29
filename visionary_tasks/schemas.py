from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .jobs.models import JobRecord
from .jobs.stages import StageStatus
from .orchestration.pipeline import download_keys

JobStatus = Literal["queued", "running", "done", "error"]


class StageStatusItem(BaseModel):
    name: str
    status: StageStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    artifact: dict[str, Any] | None = None
    error: str | None = None


class PipelineStageItem(BaseModel):
    id: str
    label: str
    order: int
    inputs: list[str] = Field(default_factory=list)


class PipelineResponse(BaseModel):
    stages: list[PipelineStageItem] = Field(default_factory=list)


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    enabled: list[str] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: JobRecord) -> "CreateJobResponse":
        return cls(
            job_id=record.job_id,
            status="queued",
            message="任务已创建",
            enabled=record.enabled,
        )


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    progress: int = Field(ge=0, le=100)
    created_at: datetime
    updated_at: datetime
    output_ply: str | None = None
    error: str | None = None
    current_stage: str | None = None
    enabled: list[str] = Field(default_factory=list)
    stages: list[StageStatusItem] = Field(default_factory=list)
    artifacts: dict[str, dict[str, Any] | None] = Field(default_factory=dict)

    @classmethod
    def from_record(cls, record: JobRecord) -> "JobStatusResponse":
        status = _derive_status(record)
        current_stage = _derive_current_stage(record)
        output_ply = _derive_output_ply(record)
        error = _derive_error(record)
        return cls(
            job_id=record.job_id,
            status=status,
            message=_derive_message(status, current_stage, error),
            progress=_derive_progress(record, status),
            created_at=record.parse_created_at(),
            updated_at=record.parse_updated_at(),
            output_ply=output_ply,
            error=error,
            current_stage=current_stage,
            enabled=record.enabled,
            stages=[
                StageStatusItem(
                    name=stage.name,
                    status=stage.status,
                    started_at=datetime.fromisoformat(stage.started_at) if stage.started_at else None,
                    ended_at=datetime.fromisoformat(stage.ended_at) if stage.ended_at else None,
                    artifact=stage.artifact,
                    error=stage.error,
                )
                for stage in record.stages
            ],
            artifacts=record.artifacts_map(),
        )


class StageArtifactResponse(BaseModel):
    job_id: str
    stage: str
    artifact: dict[str, Any]


def _derive_status(record: JobRecord) -> JobStatus:
    if not record.stages:
        return "queued"
    if any(stage.status == "error" for stage in record.stages):
        return "error"
    if all(stage.status == "done" for stage in record.stages):
        return "done"
    if any(stage.status == "running" for stage in record.stages):
        return "running"
    return "queued"


def _derive_current_stage(record: JobRecord) -> str | None:
    running_stage = next((stage for stage in record.stages if stage.status == "running"), None)
    return running_stage.name if running_stage else None


def _derive_progress(record: JobRecord, status: JobStatus) -> int:
    if not record.stages:
        return 0
    if status == "error":
        done_count = sum(1 for stage in record.stages if stage.status == "done")
        return min(99, int(done_count * 100 / len(record.stages)))
    if status == "done":
        return 100
    done_count = sum(1 for stage in record.stages if stage.status == "done")
    running_bonus = 1 if any(stage.status == "running" for stage in record.stages) else 0
    return min(99, int((done_count + running_bonus * 0.5) * 100 / len(record.stages)))


def _derive_message(
    status: JobStatus,
    current_stage: str | None,
    error: str | None,
) -> str:
    if status == "queued":
        return "任务排队中"
    if status == "running":
        return f"{current_stage} 执行中" if current_stage else "任务执行中"
    if status == "done":
        return "任务完成"
    return error or "任务失败"


def _derive_output_ply(record: JobRecord) -> str | None:
    for stage in reversed(record.stages):
        if stage.status != "done" or not isinstance(stage.artifact, dict):
            continue
        for key in download_keys(stage.name):
            if key == "ply":
                ply = stage.artifact.get("ply")
                if isinstance(ply, str):
                    return ply
    return None


def _derive_error(record: JobRecord) -> str | None:
    for stage in record.stages:
        if stage.status == "error":
            return stage.error or f"{stage.name} 失败"
    return None
