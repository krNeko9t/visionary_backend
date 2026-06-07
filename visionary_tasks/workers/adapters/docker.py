from __future__ import annotations

import logging
from typing import Any

import docker
from docker.errors import DockerException
from docker.types import DeviceRequest

logger = logging.getLogger(__name__)


def run_docker_worker(
    *,
    image: str,
    command: list[str],
    volumes: dict[str, dict[str, str]],
    use_gpu: bool = True,
    label: str = "worker",
) -> str | None:
    try:
        client = docker.from_env()
    except DockerException as exc:
        raise RuntimeError(f"Docker 不可用，无法启动 {label}: {exc}") from exc

    try:
        device_requests: list[DeviceRequest] = []
        if use_gpu:
            device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])]
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
            output = result.decode("utf-8", errors="ignore")
            logger.info("%s output: %s", label, output)
            return output
        return None
    finally:
        client.close()


def build_job_volumes(host_job_path: str, container_mount: str = "/job") -> dict[str, dict[str, str]]:
    return {host_job_path: {"bind": container_mount, "mode": "rw"}}


def extend_volumes(
    base: dict[str, dict[str, str]],
    extra: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = dict(base)
    merged.update(extra)
    return merged
