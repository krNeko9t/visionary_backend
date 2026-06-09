from __future__ import annotations

from pathlib import Path

import docker

from ..config.loader import load_gs_job_config, load_langsplat_job_config
from ..container.mount import resolve_host_job_path, resolve_host_mount_path
from ..domain.jobs import Artifact
from ..jobs.paths import JobPaths
from ..jobs.storage import append_progress_event, write_worker_result
from ..settings import Settings
from ..workers.adapters.docker import build_job_volumes, extend_volumes, run_docker_worker
from ..workers.adapters.langsplat import build_langsplat_live_code_volumes
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
    feature_levels = config.training_feature_levels()
    export_checkpoint = config.export_checkpoint()

    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="started", message="LangSplat 开始"),
    )

    client = docker.from_env()
    try:
        host_job_path = str(resolve_host_job_path(settings, paths.root, client))
        ckpts_host = runtime.ckpts_host or str(
            resolve_host_mount_path(settings, settings.ckpts_root, client)
        )
        langsplat_repo_host = (
            str(resolve_host_mount_path(settings, settings.langsplat_repo_path, client))
            if settings.langsplat_repo_path is not None
            else None
        )
    finally:
        client.close()

    sam_ckpt_relative = config.preprocess.sam_ckpt_path.removeprefix("ckpts/")
    sam_ckpt_file = Path(ckpts_host) / sam_ckpt_relative
    if not sam_ckpt_file.is_file():
        return WorkerResult(
            stage_id=STAGE_ID,
            status="error",
            error=(
                f"缺少 SAM 权重: {sam_ckpt_file}。"
                "请按 README 下载 sam_vit_h_4b8939.pth 到项目 ckpts/ 目录，"
                "并确保 task-server 已挂载 ./ckpts:/workspace/ckpts"
            ),
        )

    volumes = build_job_volumes(host_job_path, JOB_MOUNT)
    volumes = extend_volumes(volumes, {ckpts_host: {"bind": "/workspace/ckpts", "mode": "ro"}})
    if langsplat_repo_host:
        volumes = extend_volumes(volumes, build_langsplat_live_code_volumes(langsplat_repo_host))

    preprocess_cmd = config.to_preprocess_command(f"{JOB_MOUNT}/colmap")
    run_docker_worker(
        image=runtime.worker_image,
        command=preprocess_cmd,
        volumes=volumes,
        label="langsplat preprocess",
    )
    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="progress", progress=0.3, message="LangSplat preprocess 完成"),
    )

    gs_config = load_gs_job_config(settings, paths)
    checkpoint = paths.gs_checkpoint(gs_config.output_relative, gs_config.output_iteration)
    model_root = f"{JOB_MOUNT}/{runtime.model_relative}"
    gs_checkpoint_path = f"{JOB_MOUNT}/{checkpoint.relative_to(paths.root).as_posix()}"

    for index, feature_level in enumerate(feature_levels):
        train_cmd = config.to_train_command(
            source_path=f"{JOB_MOUNT}/colmap",
            model_path=model_root,
            checkpoint_path=gs_checkpoint_path,
            feature_level=feature_level,
        )
        run_docker_worker(
            image=runtime.worker_image,
            command=train_cmd,
            volumes=volumes,
            label=f"langsplat train L{feature_level}",
        )
        model_dir = paths.langsplat_model_dir(runtime.model_relative, feature_level)
        if not model_dir.is_dir() or not any(model_dir.iterdir()):
            return WorkerResult(
                stage_id=STAGE_ID,
                status="error",
                error=f"langsplat 未生成模型目录或目录为空: {model_dir.relative_to(paths.root)}",
            )
        progress = 0.3 + 0.5 * (index + 1) / len(feature_levels)
        append_progress_event(
            paths.stage_events_file(STAGE_ID),
            make_progress_event(
                STAGE_ID,
                event_type="progress",
                progress=progress,
                message=f"LangSplat 训练完成 level={feature_level}",
            ),
        )

    export_cmd = config.to_export_command(
        model_root=f"{JOB_MOUNT}/{runtime.model_relative}",
        output_dir=f"{JOB_MOUNT}/{config.export.output_relative}",
        checkpoint=export_checkpoint,
    )
    run_docker_worker(
        image=runtime.worker_image,
        command=export_cmd,
        volumes=volumes,
        label="langsplat export",
    )

    export_root = paths.langsplat_export_root(config.export.output_relative, export_checkpoint)
    if not export_root.is_dir() or not any(export_root.iterdir()):
        return WorkerResult(
            stage_id=STAGE_ID,
            status="error",
            error=f"langsplat 未生成最终产物目录或目录为空: {export_root.relative_to(paths.root)}",
        )

    artifacts = [
        Artifact(
            id="language_model",
            stage_id=STAGE_ID,
            type="directory",
            path=str(export_root.relative_to(paths.root)),
            downloadable=True,
            label="LangSplat Final Product",
            metadata={
                "checkpoint": export_checkpoint,
                "levels": config.export_levels(),
                "queries": list(config.export.queries),
            },
        )
    ]
    result = WorkerResult(stage_id=STAGE_ID, status="done", artifacts=artifacts)
    write_worker_result(paths.stage_result_file(STAGE_ID), result)
    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="completed", progress=1.0, message="LangSplat 完成"),
    )
    return result
