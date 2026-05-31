import logging

import docker
from docker.errors import DockerException
from docker.types import DeviceRequest

from ..config.loader import load_gs_job_config
from ..docker.mount import resolve_host_job_path
from ..jobs.paths import JobPaths
from ..jobs.stage_artifacts import persist_stage_artifact
from ..orchestration.inputs import missing_langsplat_inputs
from ..settings import Settings

logger = logging.getLogger(__name__)

STAGE_NAME = "langsplat"
JOB_MOUNT = "/job"


def run(settings: Settings, paths: JobPaths) -> dict[str, str]:
    missing = missing_langsplat_inputs(paths, settings)
    if missing:
        raise FileNotFoundError("; ".join(missing))
    langsplat = settings.langsplat

    try:
        client = docker.from_env()
    except DockerException as exc:
        raise RuntimeError(f"Docker 不可用，无法启动 langsplat worker: {exc}") from exc

    try:
        host_job_path = resolve_host_job_path(settings, paths.root, client)
        volumes = {str(host_job_path): {"bind": JOB_MOUNT, "mode": "rw"}}
        if langsplat.ckpts_host:
            volumes[langsplat.ckpts_host] = {"bind": "/workspace/ckpts", "mode": "ro"}
        device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])]

        preprocess_cmd = langsplat.preprocess_command(f"{JOB_MOUNT}/colmap")
        _run_container(
            client,
            langsplat.worker_image,
            preprocess_cmd,
            volumes,
            device_requests,
            "langsplat preprocess",
        )

        checkpoint = paths.gs_checkpoint(
            settings,
            load_gs_job_config(settings, paths).output_iteration,
        )
        train_cmd = langsplat.train_command(
            source_path=f"{JOB_MOUNT}/colmap",
            model_path=f"{JOB_MOUNT}/{langsplat.model_relative}",
            checkpoint_path=f"{JOB_MOUNT}/{checkpoint.relative_to(paths.root).as_posix()}",
        )
        _run_container(
            client,
            langsplat.worker_image,
            train_cmd,
            volumes,
            device_requests,
            "langsplat train",
        )
    finally:
        client.close()

    model_dir = paths.langsplat_model_dir(settings)
    if not model_dir.is_dir() or not any(model_dir.iterdir()):
        raise FileNotFoundError(
            f"langsplat 未生成模型目录或目录为空: {model_dir.relative_to(paths.root)}"
        )

    return persist_stage_artifact(
        paths,
        STAGE_NAME,
        {"model_dir": str(model_dir.relative_to(paths.root))},
    )


def _run_container(
    client: docker.DockerClient,
    image: str,
    command: list[str],
    volumes: dict,
    device_requests: list[DeviceRequest],
    label: str,
) -> None:
    result = client.containers.run(
        image,
        command=command,
        volumes=volumes,
        device_requests=device_requests,
        remove=True,
        stderr=True,
        stdout=True,
        detach=False,
    )
    if isinstance(result, bytes):
        logger.info(
            "%s worker output: %s",
            label,
            result.decode("utf-8", errors="ignore"),
        )
