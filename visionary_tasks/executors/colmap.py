import logging
import shutil
from pathlib import Path

import docker
from docker.errors import DockerException
from docker.types import DeviceRequest

from ..docker.mount import resolve_host_job_path
from ..jobs.paths import JobPaths
from ..jobs.stage_artifacts import COLMAP_OUTPUT_NAMES, persist_stage_artifact
from ..orchestration.inputs import missing_colmap_inputs
from ..settings import Settings

logger = logging.getLogger(__name__)


def run(settings: Settings, paths: JobPaths) -> dict[str, str]:
    missing = missing_colmap_inputs(paths, settings)
    if missing:
        raise FileNotFoundError(missing[0])
    try:
        client = docker.from_env()
    except DockerException as exc:
        raise RuntimeError(f"Docker 不可用，无法启动 colmap worker: {exc}") from exc

    try:
        host_job_path = resolve_host_job_path(settings, paths.root, client)
        cmd = [
            "--source_path",
            "/job",
            "--camera",
            settings.colmap_camera_model,
        ]
        volumes = {
            str(host_job_path): {"bind": "/job", "mode": "rw"},
        }
        result = client.containers.run(
            settings.colmap_worker_image,
            command=cmd,
            volumes=volumes,
            device_requests=[DeviceRequest(count=-1, capabilities=[["gpu"]])],
            remove=True,
            stderr=True,
            stdout=True,
            detach=False,
        )
        if isinstance(result, bytes):
            logger.info("colmap worker output: %s", result.decode("utf-8", errors="ignore"))
    finally:
        client.close()

    _relocate_colmap_output(paths)
    sparse_dir = paths.colmap_dir / "sparse" / "0"
    if not sparse_dir.exists():
        raise FileNotFoundError(f"COLMAP 未生成稀疏重建: {sparse_dir}")

    return persist_stage_artifact(
        paths,
        "colmap",
        {
            "sparse_dir": "colmap/sparse/0",
            "images_dir": "colmap/images",
        },
    )


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
