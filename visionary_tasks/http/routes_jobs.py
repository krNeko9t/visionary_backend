import json
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from ..config.loader import materialize_job_configs
from ..jobs.models import JobRecord
from ..jobs.paths import JobPaths
from ..jobs.storage import read_record, save_upload_files, write_record
from ..orchestration.pipeline import download_keys, pipeline_public_stages, validate_enabled
from ..orchestration.runner import run_job
from ..schemas import (
    CreateJobResponse,
    JobStatusResponse,
    PipelineResponse,
    PipelineStageItem,
    StageArtifactResponse,
)
from ..settings import get_settings

router = APIRouter()


@router.get("/api/pipeline", response_model=PipelineResponse)
def get_pipeline() -> PipelineResponse:
    return PipelineResponse(
        stages=[PipelineStageItem(**item) for item in pipeline_public_stages()],
    )


@router.post("/api/jobs", response_model=CreateJobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    enabled: str = Form(...),
    gs_config: UploadFile | None = File(None),
    colmap_config: UploadFile | None = File(None),
    langsplat_config: UploadFile | None = File(None),
    gaussian_wrapping_config: UploadFile | None = File(None),
) -> CreateJobResponse:
    settings = get_settings()
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")

    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    checked_files: list[tuple[str, bytes]] = []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in image_exts:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {upload.filename}")
        checked_files.append((upload.filename or "", await upload.read()))

    try:
        enabled_stages = _parse_enabled(enabled)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config_overrides = {
        "3dgs": await _parse_yaml_upload(gs_config, "gs_config"),
        "colmap": await _parse_yaml_upload(colmap_config, "colmap_config"),
        "langsplat": await _parse_yaml_upload(langsplat_config, "langsplat_config"),
        "gaussian-wrapping": await _parse_yaml_upload(
            gaussian_wrapping_config,
            "gaussian_wrapping_config",
        ),
    }

    job_id = uuid.uuid4().hex[:12]
    paths = JobPaths.from_settings(settings, job_id)

    saved = save_upload_files(checked_files, paths.input_dir)
    if saved == 0:
        raise HTTPException(status_code=400, detail="未检测到有效文件名")

    try:
        gs_config = materialize_job_configs(settings, paths, overrides=config_overrides)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    paths.ensure_dirs(gs_config.output_relative)

    record = JobRecord.queued(job_id, enabled_stages)
    write_record(paths.status_file, record)

    background_tasks.add_task(run_job, settings, paths, enabled_stages)
    return CreateJobResponse.from_record(record)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    settings = get_settings()
    paths = JobPaths.from_settings(settings, job_id)
    record = read_record(paths.status_file)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobStatusResponse.from_record(record)


@router.get("/api/jobs/{job_id}/download/3dgs")
def download_3dgs(job_id: str) -> FileResponse:
    return _download_stage_file(job_id, "3dgs")


@router.get("/api/jobs/{job_id}/download/mesh")
def download_mesh(job_id: str) -> FileResponse:
    return _download_stage_file(job_id, "gaussian-wrapping")


@router.get("/api/jobs/{job_id}/result")
def get_result(job_id: str) -> FileResponse:
    settings = get_settings()
    paths = JobPaths.from_settings(settings, job_id)
    record = read_record(paths.status_file)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    response_payload = JobStatusResponse.from_record(record)
    output_ply = response_payload.output_ply
    if response_payload.status != "done" or not output_ply:
        raise HTTPException(status_code=409, detail="任务尚未完成")

    output_file = paths.artifact(output_ply)
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    return FileResponse(output_file, filename=f"{job_id}.ply")


@router.get("/api/jobs/{job_id}/artifacts/{stage}")
def get_stage_artifact(job_id: str, stage: str) -> Response:
    settings = get_settings()
    paths = JobPaths.from_settings(settings, job_id)
    record = read_record(paths.status_file)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if stage not in record.enabled:
        raise HTTPException(status_code=404, detail=f"阶段不存在: {stage}")
    artifact = record.stage_artifact(stage)
    if artifact is None:
        raise HTTPException(status_code=409, detail="该阶段尚未产出结果")
    ply_file = _resolve_artifact_file(paths, record, stage)
    if ply_file is not None and ply_file.exists():
        return FileResponse(ply_file, filename=f"{job_id}-{stage}.ply")
    return StageArtifactResponse(job_id=job_id, stage=stage, artifact=artifact)


def _download_stage_file(job_id: str, stage: str) -> FileResponse:
    settings = get_settings()
    paths = JobPaths.from_settings(settings, job_id)
    record = read_record(paths.status_file)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    ply_file = _resolve_artifact_file(paths, record, stage)
    if ply_file is None:
        raise HTTPException(status_code=409, detail=f"{stage} 阶段尚未产出结果")
    if not ply_file.exists():
        raise HTTPException(status_code=404, detail=f"{stage} 文件不存在")
    suffix = "mesh" if stage == "gaussian-wrapping" else stage
    return FileResponse(ply_file, filename=f"{job_id}-{suffix}.ply")


def _resolve_artifact_file(
    paths: JobPaths,
    record: JobRecord,
    stage: str,
) -> Path | None:
    artifact = record.stage_artifact(stage)
    if not isinstance(artifact, dict):
        return None
    for key in download_keys(stage):
        relative = artifact.get(key)
        if isinstance(relative, str):
            return paths.artifact(relative)
    return None


def _parse_enabled(raw_enabled: str) -> list[str]:
    text = raw_enabled.strip()
    if not text:
        raise ValueError("enabled 不能为空")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"enabled JSON 解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("enabled 必须是对象，例如 {\"colmap\":true,\"3dgs\":true}")
    normalized: dict[str, bool] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError("enabled 的键必须是字符串")
        if not isinstance(value, bool):
            raise ValueError(f"enabled[{key}] 必须是布尔值")
        normalized[key.strip()] = value
    return validate_enabled(normalized)


async def _parse_yaml_upload(
    upload: UploadFile | None,
    field_name: str,
) -> dict[str, Any] | None:
    if upload is None or not upload.filename:
        return None
    try:
        payload = yaml.safe_load(await upload.read())
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} YAML 解析失败: {exc}",
        ) from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} 根节点必须是对象")
    return payload
