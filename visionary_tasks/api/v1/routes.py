from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ...domain.input_modes import get_input_mode
from ...domain.jobs import JobSpec
from ...domain.pipeline import INPUT_MODE_DEFINITIONS
from ...services.job_service import JobService
from ...settings import get_settings
from .schemas import (
    ArtifactListResponse,
    ArtifactItem,
    CancelJobResponse,
    CapabilitiesResponse,
    CreateJobResponse,
    EventListResponse,
    JobSpecRequest,
    JobStatusResponse,
    ProgressEventItem,
)

router = APIRouter(prefix="/api/v1")


def _service() -> JobService:
    return JobService(get_settings())


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities() -> CapabilitiesResponse:
    payload = JobService.capabilities()
    return CapabilitiesResponse(**payload)


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    spec: str = Form(...),
) -> CreateJobResponse:
    service = _service()

    try:
        spec_payload = json.loads(spec)
        job_spec = JobSpecRequest.model_validate(spec_payload).to_domain()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"spec 解析失败: {exc}") from exc

    try:
        checked_files = await _read_upload_files(files, job_spec)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        state = service.create_job(job_spec, checked_files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(service.run_job_async, state.job_id)
    return CreateJobResponse(
        job_id=state.job_id,
        status="queued",
        message="任务已创建",
        outputs=list(state.spec.outputs),
        planned_stages=list(state.planned_stages),
    )


async def _read_upload_files(
    uploads: list[UploadFile],
    spec: JobSpec,
) -> list[tuple[str, bytes]]:
    if not uploads:
        raise ValueError("请至少上传一个文件")

    input_mode = get_input_mode(spec)
    allowed_exts = set(INPUT_MODE_DEFINITIONS[input_mode].file_types)
    checked_files: list[tuple[str, bytes]] = []
    for upload in uploads:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in allowed_exts:
            raise ValueError(f"input_mode={input_mode} 不支持的文件类型: {upload.filename}")
        checked_files.append((upload.filename or "", await upload.read()))
    return checked_files


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    state = _service().get_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobStatusResponse.from_state(state)


@router.get("/jobs/{job_id}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(job_id: str) -> ArtifactListResponse:
    service = _service()
    state = service.get_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ArtifactListResponse(
        job_id=job_id,
        artifacts=[ArtifactItem.from_domain(artifact) for artifact in state.artifacts],
    )


@router.get("/jobs/{job_id}/artifacts/{artifact_id}/download")
def download_artifact(job_id: str, artifact_id: str) -> FileResponse:
    service = _service()
    state = service.get_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    artifact = state.artifact_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"产物不存在: {artifact_id}")
    if not artifact.downloadable:
        raise HTTPException(status_code=400, detail=f"产物不可下载: {artifact_id}")

    file_path = service.get_artifact_path(job_id, artifact_id)
    if file_path is None:
        if state.status != "done":
            raise HTTPException(status_code=409, detail="任务尚未完成")
        raise HTTPException(status_code=404, detail="产物文件不存在")

    return FileResponse(file_path, filename=f"{job_id}-{artifact_id}{file_path.suffix}")


@router.get("/jobs/{job_id}/events", response_model=EventListResponse)
def list_events(job_id: str) -> EventListResponse:
    service = _service()
    state = service.get_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    events = service.list_events(job_id)
    return EventListResponse(
        job_id=job_id,
        events=[ProgressEventItem.from_domain(event) for event in events],
    )


@router.post("/jobs/{job_id}/cancel", response_model=CancelJobResponse)
def cancel_job(job_id: str) -> CancelJobResponse:
    state = _service().request_cancel(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return CancelJobResponse(
        job_id=job_id,
        status=state.status,
        message="取消请求已记录" if state.cancel_requested else "任务已结束，无法取消",
    )
