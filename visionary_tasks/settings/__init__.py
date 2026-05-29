import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .gaussian_wrapping import GaussianWrappingSettings
from .langsplat import LangSplatSettings

__all__ = [
    "Settings",
    "GaussianWrappingSettings",
    "LangSplatSettings",
    "get_settings",
]


@dataclass(frozen=True)
class Settings:
    data_root: Path
    jobs_root: Path
    colmap_worker_image: str
    colmap_camera_model: str
    gs_iterations: int
    gs_save_iteration: int
    gs_output_relative: str
    gs_repo_path: Path
    task_server_container_name: str
    wrapping: GaussianWrappingSettings
    langsplat: LangSplatSettings


@lru_cache
def get_settings() -> Settings:
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    jobs_root = Path(os.getenv("JOBS_ROOT", str(data_root / "jobs")))
    gs_repo_path = Path(os.getenv("GS_REPO_PATH", "/workspace/gaussian-splatting"))
    gs_save_iteration = int(os.getenv("GS_SAVE_ITERATION", "500"))
    return Settings(
        data_root=data_root,
        jobs_root=jobs_root,
        colmap_worker_image=os.getenv("COLMAP_WORKER_IMAGE", "visionary-colmap-worker:local"),
        colmap_camera_model=os.getenv("COLMAP_CAMERA_MODEL", "OPENCV"),
        gs_iterations=int(os.getenv("GS_ITERATIONS", "30000")),
        gs_save_iteration=gs_save_iteration,
        gs_output_relative=os.getenv("GS_OUTPUT_RELATIVE", "output"),
        gs_repo_path=gs_repo_path,
        task_server_container_name=os.getenv(
            "TASK_SERVER_CONTAINER_NAME",
            "visionary-task-server",
        ),
        wrapping=GaussianWrappingSettings.from_env(gs_save_iteration),
        langsplat=LangSplatSettings.from_env(),
    )
