from __future__ import annotations

import shutil

from ..config.loader import load_colmap_job_config
from ..container.mount import resolve_host_job_path
from ..domain.jobs import Artifact
from ..jobs.paths import JobPaths
from ..jobs.storage import append_progress_event, write_worker_result
from ..settings import Settings
from ..workers.adapters.docker import build_job_volumes, run_docker_worker
from ..workers.contract import WorkerResult, make_progress_event
from .inputs import missing_colmap_inputs

COLMAP_OUTPUT_NAMES = (
    "sparse",
    "images",
    "distorted",
    "stereo",
    "run-colmap-geometric.sh",
    "run-colmap-photometric.sh",
)


def run(settings: Settings, paths: JobPaths) -> WorkerResult:
    stage_id = "colmap"
    missing = missing_colmap_inputs(paths, settings)
    if missing:
        return _error_result(stage_id, missing[0])

    paths.stage_dir(stage_id).mkdir(parents=True, exist_ok=True)
    config = load_colmap_job_config(settings, paths)

    append_progress_event(
        paths.stage_events_file(stage_id),
        make_progress_event(stage_id, event_type="started", message="COLMAP 开始"),
    )

    import docker

    client = docker.from_env()
    try:
        host_job_path = str(resolve_host_job_path(settings, paths.root, client))
    finally:
        client.close()

    logs = run_docker_worker(
        image=config.worker_image,
        command=config.to_convert_command("/job"),
        volumes=build_job_volumes(host_job_path),
        label="colmap",
    )

    _relocate_colmap_output(paths)
    sparse_dir = paths.colmap_dir / "sparse" / "0"
    if not sparse_dir.exists():
        return _error_result(stage_id, f"COLMAP 未生成稀疏重建: {sparse_dir}")

    artifacts = [
        Artifact(
            id="colmap_sparse",
            stage_id=stage_id,
            type="directory",
            path="colmap/sparse/0",
            downloadable=False,
            label="COLMAP Sparse Reconstruction",
        ),
        Artifact(
            id="colmap_images",
            stage_id=stage_id,
            type="directory",
            path="colmap/images",
            downloadable=False,
            label="COLMAP Images",
        ),
    ]
    result = WorkerResult(stage_id=stage_id, status="done", artifacts=artifacts, logs=logs)
    write_worker_result(paths.stage_result_file(stage_id), result)
    append_progress_event(
        paths.stage_events_file(stage_id),
        make_progress_event(stage_id, event_type="completed", progress=1.0, message="COLMAP 完成"),
    )
    return result


def _relocate_colmap_output(paths: JobPaths) -> None:
    paths.colmap_dir.mkdir(parents=True, exist_ok=True)
    for name in COLMAP_OUTPUT_NAMES:
        source = paths.root / name
        if not source.exists():
            continue
        destination = paths.colmap_dir / name
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.move(str(source), str(destination))


def _error_result(stage_id: str, error: str) -> WorkerResult:
    return WorkerResult(stage_id=stage_id, status="error", error=error)
