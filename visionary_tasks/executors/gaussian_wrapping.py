import logging

import docker
from docker.errors import DockerException
from docker.types import DeviceRequest

from ..config.loader import load_gaussian_wrapping_job_config
from ..docker.mount import resolve_host_job_path
from ..jobs.paths import JobPaths
from ..jobs.stage_artifacts import persist_stage_artifact
from ..orchestration.inputs import missing_gaussian_wrapping_inputs
from ..settings import Settings

logger = logging.getLogger(__name__)

STAGE_NAME = "gaussian-wrapping"


def run(settings: Settings, paths: JobPaths) -> dict[str, str]:
    missing = missing_gaussian_wrapping_inputs(paths, settings)
    if missing:
        raise FileNotFoundError("; ".join(missing))
    config = load_gaussian_wrapping_job_config(settings, paths)
    wrapping = settings.wrapping

    try:
        client = docker.from_env()
    except DockerException as exc:
        raise RuntimeError(f"Docker 不可用，无法启动 gaussian-wrapping worker: {exc}") from exc

    try:
        host_job_path = resolve_host_job_path(settings, paths.root, client)
        cmd = config.to_container_command("/job/colmap", "/job/output")
        volumes = {str(host_job_path): {"bind": "/job", "mode": "rw"}}
        result = client.containers.run(
            wrapping.worker_image,
            command=cmd,
            volumes=volumes,
            device_requests=[DeviceRequest(count=-1, capabilities=[["gpu"]])],
            remove=True,
            stderr=True,
            stdout=True,
            detach=False,
        )
        if isinstance(result, bytes):
            logger.info(
                "gaussian-wrapping worker output: %s",
                result.decode("utf-8", errors="ignore"),
            )
    finally:
        client.close()

    mesh_ply_names = tuple(config.outputs.mesh_ply_names)
    mesh_textured_ply_names = tuple(config.outputs.mesh_textured_ply_names)
    mesh_ply = paths.wrapping_mesh_ply(settings, mesh_ply_names)
    mesh_textured_ply = paths.wrapping_mesh_textured_ply(settings, mesh_textured_ply_names)
    if mesh_ply is None and mesh_textured_ply is None:
        raise FileNotFoundError(
            "gaussian-wrapping 未生成 mesh 文件，"
            f"已检查: {mesh_ply_names}, {mesh_textured_ply_names}"
        )

    payload: dict[str, str] = {}
    if mesh_ply is not None:
        payload["mesh_ply"] = str(mesh_ply.relative_to(paths.root))
    if mesh_textured_ply is not None:
        payload["mesh_textured_ply"] = str(mesh_textured_ply.relative_to(paths.root))
    return persist_stage_artifact(paths, STAGE_NAME, payload)
