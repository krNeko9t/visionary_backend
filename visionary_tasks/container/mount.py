from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..settings import Settings

if TYPE_CHECKING:
    from docker import DockerClient

SAM_CKPT_FILENAME = "sam_vit_h_4b8939.pth"


@dataclass(frozen=True)
class MountedAsset:
    """容器内挂载目录下的单个文件；检查、worker 路径与 Docker 卷绑定统一由此解析。"""

    mount_root: Path
    filename: str

    @classmethod
    def sam_checkpoint(cls, settings: Settings) -> MountedAsset:
        return cls(settings.ckpts_root, SAM_CKPT_FILENAME)

    @property
    def container_path(self) -> Path:
        return self.mount_root / self.filename

    @property
    def worker_path(self) -> str:
        return self.container_path.as_posix()

    def missing_error(self) -> str | None:
        if self.container_path.is_file():
            return None
        return (
            f"缺少 SAM 权重: {self.worker_path}。"
            f"请将 {self.filename} 放到项目 ckpts/ 目录，"
            f"并确保 task-server 已挂载 ./ckpts:{self.mount_root.as_posix()}"
        )

    def docker_volume(
        self,
        settings: Settings,
        client: DockerClient,
    ) -> dict[str, dict[str, str]]:
        host = str(resolve_host_mount_path(settings, self.mount_root, client))
        bind = self.mount_root.as_posix()
        return {host: {"bind": bind, "mode": "ro"}}


def resolve_host_mount_path(
    settings: Settings,
    container_path: Path,
    client: DockerClient,
) -> Path:
    task_container = client.containers.get(settings.task_server_container_name)
    mounts = task_container.attrs.get("Mounts", [])
    target = container_path.as_posix().rstrip("/")
    for mount in mounts:
        destination = str(mount.get("Destination", "")).rstrip("/")
        source = mount.get("Source")
        if destination == target and source:
            return Path(source)
    raise RuntimeError(f"无法解析容器挂载的宿主机路径: {target}")


def resolve_host_job_path(
    settings: Settings,
    job_root: Path,
    client: DockerClient,
) -> Path:
    task_container = client.containers.get(settings.task_server_container_name)
    mounts = task_container.attrs.get("Mounts", [])
    job_root_str = job_root.as_posix()
    for mount in mounts:
        destination = mount.get("Destination")
        source = mount.get("Source")
        if not destination or not source:
            continue
        destination_posix = str(destination).rstrip("/")
        if job_root_str.startswith(destination_posix):
            relative = job_root_str[len(destination_posix) :].lstrip("/")
            if relative:
                return Path(source) / relative
            return Path(source)
    raise RuntimeError(f"无法解析 job 目录的宿主机路径: {job_root_str}")
