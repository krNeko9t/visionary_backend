from __future__ import annotations

import docker

from ..config.loader import load_gs_job_config, load_langsplat_job_config
from ..container.mount import resolve_host_job_path
from ..domain.jobs import Artifact
from ..jobs.paths import JobPaths
from ..jobs.storage import append_progress_event, write_worker_result
from ..settings import Settings
from ..workers.adapters.docker import build_job_volumes, extend_volumes, run_docker_worker
from ..workers.contract import WorkerResult, make_progress_event
from .inputs import missing_langsplat_inputs

STAGE_ID = "langsplat"
JOB_MOUNT = "/job"


def run(settings: Settings, paths: JobPaths) -> WorkerResult:
    missing = missing_langsplat_inputs(paths, settings)
    if missing:
        return WorkerResult(stage_id=STAGE_ID, status="error", error="; ".join(missing))

    stage_dir = paths.stage_dir(STAGE_ID)
    stage_dir.mkdir(parents=True, exist_ok=True)
    config = load_langsplat_job_config(settings, paths)
    runtime = config.runtime

    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="started", message="LangSplat 开始"),
    )

    client = docker.from_env()
    try:
        host_job_path = str(resolve_host_job_path(settings, paths.root, client))
    finally:
        client.close()

    volumes = build_job_volumes(host_job_path, JOB_MOUNT)
    if runtime.ckpts_host:
        volumes = extend_volumes(volumes, {runtime.ckpts_host: {"bind": "/workspace/ckpts", "mode": "ro"}})

    preprocess_cmd = config.to_preprocess_command(f"{JOB_MOUNT}/colmap")
    run_docker_worker(
        image=runtime.worker_image,
        command=preprocess_cmd,
        volumes=volumes,
        label="langsplat preprocess",
    )
    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="progress", progress=0.5, message="LangSplat preprocess 完成"),
    )

    gs_config = load_gs_job_config(settings, paths)
    checkpoint = paths.gs_checkpoint(gs_config.output_relative, gs_config.output_iteration)
    train_cmd = config.to_train_command(
        source_path=f"{JOB_MOUNT}/colmap",
        model_path=f"{JOB_MOUNT}/{runtime.model_relative}",
        checkpoint_path=f"{JOB_MOUNT}/{checkpoint.relative_to(paths.root).as_posix()}",
    )
    run_docker_worker(
        image=runtime.worker_image,
        command=train_cmd,
        volumes=volumes,
        label="langsplat train",
    )

    model_dir = paths.langsplat_model_dir(runtime.model_relative)
    if not model_dir.is_dir() or not any(model_dir.iterdir()):
        return WorkerResult(
            stage_id=STAGE_ID,
            status="error",
            error=f"langsplat 未生成模型目录或目录为空: {model_dir.relative_to(paths.root)}",
        )

    artifacts = [
        Artifact(
            id="language_model",
            stage_id=STAGE_ID,
            type="directory",
            path=str(model_dir.relative_to(paths.root)),
            downloadable=False,
            label="LangSplat Model",
        )
    ]
    result = WorkerResult(stage_id=STAGE_ID, status="done", artifacts=artifacts)
    write_worker_result(paths.stage_result_file(STAGE_ID), result)
    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="completed", progress=1.0, message="LangSplat 完成"),
    )
    return result
