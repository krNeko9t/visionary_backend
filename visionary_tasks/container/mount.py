from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..settings import Settings

if TYPE_CHECKING:
    from docker import DockerClient


def resolve_host_job_path(
    settings: Settings,
    job_root: Path,
    client: DockerClient,
) -> Path:
    task_container = client.containers.get(settings.task_server_container_name)
    mounts = task_container.attrs.get("Mounts", [])
    job_root_str = str(job_root)
    for mount in mounts:
        destination = mount.get("Destination")
        source = mount.get("Source")
        if not destination or not source:
            continue
        if job_root_str.startswith(destination):
            relative = job_root_str[len(destination) :].lstrip("/")
            if relative:
                return Path(source) / relative
            return Path(source)
    raise RuntimeError(f"无法解析 job 目录的宿主机路径: {job_root_str}")
