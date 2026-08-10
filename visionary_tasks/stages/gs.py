from __future__ import annotations

import docker

from ..config.loader import load_gs_job_config
from ..container.mount import resolve_host_job_path
from ..domain.jobs import Artifact
from ..jobs.paths import JobPaths
from ..jobs.storage import append_progress_event, write_worker_result
from ..settings import Settings
from ..workers.adapters.docker import build_job_volumes, run_docker_worker
from ..workers.contract import WorkerResult, make_progress_event
from .inputs import missing_3dgs_inputs


def run(settings: Settings, paths: JobPaths) -> WorkerResult:
    stage_id = "3dgs"
    missing = missing_3dgs_inputs(paths, settings)
    if missing:
        return WorkerResult(stage_id=stage_id, status="error", error=missing[0])

    stage_dir = paths.stage_dir(stage_id)
    stage_dir.mkdir(parents=True, exist_ok=True)
    config = load_gs_job_config(settings, paths)

    append_progress_event(
        paths.stage_events_file(stage_id),
        make_progress_event(stage_id, event_type="started", message="3DGS 训练开始"),
    )

    client = docker.from_env()
    try:
        host_job_path = str(resolve_host_job_path(settings, paths.root, client))
    finally:
        client.close()

    logs = run_docker_worker(
        image=config.worker_image,
        command=config.to_train_command(
            "/job/colmap",
            f"/job/{config.output_relative}",
        ),
        volumes=build_job_volumes(host_job_path),
        label="3dgs",
    )

    ply = paths.gs_output_ply(config.output_relative, config.output_iteration)
    if not ply.exists():
        return WorkerResult(stage_id=stage_id, status="error", error=f"找不到 3DGS 输出文件: {ply}")

    checkpoint = paths.gs_checkpoint(config.output_relative, config.output_iteration)
    artifacts = [
        Artifact(
            id="point_cloud",
            stage_id=stage_id,
            type="ply",
            path=str(ply.relative_to(paths.root)),
            mime="application/octet-stream",
            label="3D Gaussian Point Cloud",
        ),
    ]
    if checkpoint.exists():
        artifacts.append(
            Artifact(
                id="gs_checkpoint",
                stage_id=stage_id,
                type="checkpoint",
                path=str(checkpoint.relative_to(paths.root)),
                downloadable=False,
                label="3DGS Checkpoint",
            )
        )

    result = WorkerResult(stage_id=stage_id, status="done", artifacts=artifacts, logs=logs)
    write_worker_result(paths.stage_result_file(stage_id), result)
    append_progress_event(
        paths.stage_events_file(stage_id),
        make_progress_event(
            stage_id,
            event_type="completed",
            progress=1.0,
            iteration=config.output_iteration,
            total_iterations=config.output_iteration,
            message="3DGS 训练完成",
        ),
    )
    return result
