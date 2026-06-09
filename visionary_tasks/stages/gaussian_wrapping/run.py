from __future__ import annotations

import docker

from ...config.loader import load_gaussian_wrapping_job_config, load_gs_job_config
from ...container.mount import resolve_host_job_path
from ...domain.jobs import Artifact
from ...jobs.paths import JobPaths
from ...jobs.storage import append_progress_event, write_worker_result
from ...settings import Settings
from ...workers.adapters.docker import build_job_volumes, run_docker_worker
from ...workers.contract import WorkerResult, make_progress_event
from ..inputs import missing_gaussian_wrapping_inputs
from .build_extract_command import build_extract_command
from .predict_output_names import predict_output_names
from .resolve_3dgs_output_for_extract import resolve

STAGE_ID = "gaussian-wrapping"


def run(settings: Settings, paths: JobPaths) -> WorkerResult:
    missing = missing_gaussian_wrapping_inputs(paths, settings)
    if missing:
        return WorkerResult(stage_id=STAGE_ID, status="error", error="; ".join(missing))

    stage_dir = paths.stage_dir(STAGE_ID)
    stage_dir.mkdir(parents=True, exist_ok=True)
    config = load_gaussian_wrapping_job_config(settings, paths)
    gs_config = load_gs_job_config(settings, paths)
    upstream = resolve(paths, gs_config)
    output_relative = gs_config.output_relative

    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="started", message="Mesh 提取开始"),
    )

    client = docker.from_env()
    try:
        host_job_path = str(resolve_host_job_path(settings, paths.root, client))
    finally:
        client.close()

    logs = run_docker_worker(
        image=config.worker_image,
        command=build_extract_command(config, upstream),
        volumes=build_job_volumes(host_job_path),
        label="gaussian-wrapping",
    )

    predicted = predict_output_names(config)
    mesh_ply = paths.wrapping_mesh_ply(output_relative, (predicted.mesh_ply,))
    mesh_textured_ply = None
    if predicted.mesh_textured_ply is not None:
        mesh_textured_ply = paths.wrapping_mesh_textured_ply(
            output_relative,
            (predicted.mesh_textured_ply,),
        )
    if mesh_ply is None and mesh_textured_ply is None:
        expected = [predicted.mesh_ply]
        if predicted.mesh_textured_ply is not None:
            expected.append(predicted.mesh_textured_ply)
        return WorkerResult(
            stage_id=STAGE_ID,
            status="error",
            error=(
                "gaussian-wrapping 未生成 mesh 文件，"
                f"已检查: {expected}"
            ),
        )

    artifacts: list[Artifact] = []
    if mesh_ply is not None:
        artifacts.append(
            Artifact(
                id="mesh",
                stage_id=STAGE_ID,
                type="ply",
                path=str(mesh_ply.relative_to(paths.root)),
                mime="application/octet-stream",
                label="Mesh",
            )
        )
    if mesh_textured_ply is not None:
        artifacts.append(
            Artifact(
                id="mesh_textured",
                stage_id=STAGE_ID,
                type="ply",
                path=str(mesh_textured_ply.relative_to(paths.root)),
                mime="application/octet-stream",
                label="Textured Mesh",
            )
        )

    result = WorkerResult(stage_id=STAGE_ID, status="done", artifacts=artifacts, logs=logs)
    write_worker_result(paths.stage_result_file(STAGE_ID), result)
    append_progress_event(
        paths.stage_events_file(STAGE_ID),
        make_progress_event(STAGE_ID, event_type="completed", progress=1.0, message="Mesh 完成"),
    )
    return result
