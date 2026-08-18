from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..settings import Settings

if TYPE_CHECKING:
    from docker import DockerClient

SAM_CKPT_FILENAME = "sam_vit_h_4b8939.pth"
MODEL_CACHE_RELATIVE = Path("cache/models")
MODEL_CACHE_WORKER_ROOT = Path("/cache/models")


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


@dataclass(frozen=True)
class MountedModelCache:
    """跨一次性 worker 复用的可写模型下载缓存。"""

    task_path: Path
    worker_path: Path = MODEL_CACHE_WORKER_ROOT

    @classmethod
    def from_settings(cls, settings: Settings) -> MountedModelCache:
        return cls(settings.data_root / MODEL_CACHE_RELATIVE)

    @property
    def worker_environment(self) -> dict[str, str]:
        huggingface_root = self.worker_path / "huggingface"
        return {
            "HF_HOME": huggingface_root.as_posix(),
            "HF_HUB_CACHE": (huggingface_root / "hub").as_posix(),
            "TORCH_HOME": (self.worker_path / "torch").as_posix(),
        }

    def docker_volume(
        self,
        settings: Settings,
        client: DockerClient,
    ) -> dict[str, dict[str, str]]:
        self.task_path.mkdir(parents=True, exist_ok=True)
        host = str(resolve_host_path(settings, self.task_path, client))
        return {host: {"bind": self.worker_path.as_posix(), "mode": "rw"}}


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


def resolve_host_path(
    settings: Settings,
    container_path: Path,
    client: DockerClient,
) -> Path:
    """把 task-server 内的路径映射为宿主机路径，支持挂载点下的子目录。"""

    task_container = client.containers.get(settings.task_server_container_name)
    mounts = task_container.attrs.get("Mounts", [])
    target = Path(container_path.as_posix())
    candidates: list[tuple[int, Path]] = []
    for mount in mounts:
        destination = mount.get("Destination")
        source = mount.get("Source")
        if not destination or not source:
            continue
        destination_path = Path(str(destination).rstrip("/") or "/")
        try:
            relative = target.relative_to(destination_path)
        except ValueError:
            continue
        candidates.append((len(destination_path.parts), Path(str(source)) / relative))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    raise RuntimeError(f"无法解析容器路径对应的宿主机路径: {target.as_posix()}")


def resolve_host_job_path(
    settings: Settings,
    job_root: Path,
    client: DockerClient,
) -> Path:
    return resolve_host_path(settings, job_root, client)
