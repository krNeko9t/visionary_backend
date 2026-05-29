from pathlib import Path

import docker

from ..settings import Settings


def resolve_host_job_path(
    settings: Settings,
    job_root: Path,
    client: docker.DockerClient,
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
