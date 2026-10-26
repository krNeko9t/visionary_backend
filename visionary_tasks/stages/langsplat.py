from __future__ import annotations

import docker
from visionary_progress import ProgressReporter

from ..config.loader import load_gs_job_config, load_langsplat_job_config
from ..container.mount import (
    MountedAsset,
    MountedModelCache,
    resolve_host_job_path,
)
from ..domain.jobs import Artifact
from ..jobs.paths import JobPaths
from ..jobs.storage import write_worker_result
from ..settings import Settings
from ..workers.adapters.docker import build_job_volumes, extend_volumes, run_docker_worker
from ..workers.contract import WorkerResult
from .inputs import missing_langsplat_inputs
from .progress import langsplat_progress_steps

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
    steps = langsplat_progress_steps(config)
    export_checkpoint = config.export_checkpoint()
    sam_ckpt = MountedAsset.sam_checkpoint(settings)
    model_cache = MountedModelCache.from_settings(settings)

    progress_file = paths.stage_events_file(STAGE_ID)
    container_progress_file = f"{JOB_MOUNT}/{progress_file.relative_to(paths.root).as_posix()}"
    preprocess_progress = ProgressReporter(progress_file, STAGE_ID, steps[0].id, steps[0].label)
    preprocess_progress.record(event_type="started", progress=0.0, message="LangSplat preprocess 开始")

    def worker_environment(reporter: ProgressReporter) -> dict[str, str]:
        environment = {**model_cache.worker_environment, **reporter.environment()}
        environment["VISIONARY_PROGRESS_FILE"] = container_progress_file
        return environment

    if sam_error := sam_ckpt.missing_error():
        return WorkerResult(stage_id=STAGE_ID, status="error", error=sam_error)

    client = docker.from_env()
    try:
        host_job_path = str(resolve_host_job_path(settings, paths.root, client))
        volumes = build_job_volumes(host_job_path, JOB_MOUNT)
        volumes = extend_volumes(volumes, sam_ckpt.docker_volume(settings, client))
        volumes = extend_volumes(volumes, model_cache.docker_volume(settings, client))
    finally:
        client.close()

    preprocess_cmd = config.to_preprocess_command(
        f"{JOB_MOUNT}/colmap",
        sam_ckpt_path=sam_ckpt.worker_path,
    )
    run_docker_worker(
        image=runtime.worker_image,
        command=preprocess_cmd,
        volumes=volumes,
        environment=worker_environment(preprocess_progress),
        label="langsplat preprocess",
    )
    preprocess_progress.record(event_type="step_completed", progress=1.0, message="LangSplat preprocess 完成")

    gs_config = load_gs_job_config(settings, paths)
    checkpoint = paths.gs_checkpoint(gs_config.output_relative, gs_config.output_iteration)
    model_root = f"{JOB_MOUNT}/{runtime.model_relative}"
    gs_checkpoint_path = f"{JOB_MOUNT}/{checkpoint.relative_to(paths.root).as_posix()}"
    for step in steps[1:-1]:
        feature_level = int(step.id["level"])
        training_progress = ProgressReporter(progress_file, STAGE_ID, step.id, step.label)
        training_progress.record(event_type="step_started", message=f"启动训练 level={feature_level}")
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
            environment=worker_environment(training_progress),
            label=f"langsplat train L{feature_level}",
        )
        model_dir = paths.langsplat_model_dir(runtime.model_relative, feature_level)
        if not model_dir.is_dir() or not any(model_dir.iterdir()):
            return WorkerResult(
                stage_id=STAGE_ID,
                status="error",
                error=f"langsplat 未生成模型目录或目录为空: {model_dir.relative_to(paths.root)}",
            )
        training_progress.record(event_type="step_completed", progress=1.0, message=f"LangSplat 训练完成 level={feature_level}")

    export_progress = ProgressReporter(progress_file, STAGE_ID, steps[-1].id, steps[-1].label)
    export_progress.record(event_type="step_started", progress=0.0, message="LangSplat export 开始")
    export_cmd = config.to_export_command(
        model_root=f"{JOB_MOUNT}/{runtime.model_relative}",
        output_dir=f"{JOB_MOUNT}/{config.export.output_relative}",
        checkpoint=export_checkpoint,
    )
    run_docker_worker(
        image=runtime.worker_image,
        command=export_cmd,
        volumes=volumes,
        environment=worker_environment(export_progress),
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
    export_progress.record(event_type="completed", progress=1.0, message="LangSplat 完成")
    return result
