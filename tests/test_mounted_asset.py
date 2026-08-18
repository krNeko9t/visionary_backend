from pathlib import Path
from unittest.mock import MagicMock

from visionary_tasks.container.mount import MountedAsset, MountedModelCache, SAM_CKPT_FILENAME
from visionary_tasks.settings import CorsSettings, Settings


def _settings(ckpts_root: Path) -> Settings:
    return Settings(
        data_root=Path("/data"),
        jobs_root=Path("/data/jobs"),
        ckpts_root=ckpts_root,
        langsplat_repo_path=None,
        task_server_container_name="visionary-task-server",
        cors=CorsSettings(
            allow_origins=("http://localhost:5173",),
            allow_credentials=False,
            allow_methods=("GET", "POST"),
            allow_headers=("*",),
        ),
    )


def test_sam_checkpoint_paths():
    ckpts_root = Path("/workspace/ckpts")
    asset = MountedAsset.sam_checkpoint(_settings(ckpts_root))
    assert asset.filename == SAM_CKPT_FILENAME
    assert asset.worker_path == "/workspace/ckpts/sam_vit_h_4b8939.pth"


def test_missing_error_when_file_absent(tmp_path: Path):
    asset = MountedAsset.sam_checkpoint(_settings(tmp_path / "ckpts"))
    error = asset.missing_error()
    assert error is not None
    assert (tmp_path / "ckpts" / SAM_CKPT_FILENAME).as_posix() in error
    assert SAM_CKPT_FILENAME in error
    assert "C:\\" not in error


def test_missing_error_when_file_present(tmp_path: Path):
    ckpts_root = tmp_path / "ckpts"
    ckpts_root.mkdir()
    (ckpts_root / SAM_CKPT_FILENAME).write_bytes(b"x")
    asset = MountedAsset.sam_checkpoint(_settings(ckpts_root))
    assert asset.missing_error() is None


def test_docker_volume_uses_container_bind(tmp_path: Path):
    ckpts_root = Path("/workspace/ckpts")
    asset = MountedAsset.sam_checkpoint(_settings(ckpts_root))
    client = MagicMock()
    client.containers.get.return_value = MagicMock(
        attrs={
            "Mounts": [
                {
                    "Destination": "/workspace/ckpts",
                    "Source": "/host/project/ckpts",
                }
            ]
        }
    )
    volume = asset.docker_volume(_settings(ckpts_root), client)
    assert len(volume) == 1
    bind = next(iter(volume.values()))
    assert bind == {"bind": "/workspace/ckpts", "mode": "ro"}


def test_model_cache_uses_shared_writable_data_mount(tmp_path: Path):
    settings = Settings(
        data_root=tmp_path / "data",
        jobs_root=tmp_path / "data/jobs",
        ckpts_root=tmp_path / "ckpts",
        langsplat_repo_path=None,
        task_server_container_name="visionary-task-server",
        cors=CorsSettings(
            allow_origins=("http://localhost:5173",),
            allow_credentials=False,
            allow_methods=("GET", "POST"),
            allow_headers=("*",),
        ),
    )
    cache = MountedModelCache.from_settings(settings)
    client = MagicMock()
    client.containers.get.return_value = MagicMock(
        attrs={
            "Mounts": [
                {
                    "Destination": settings.data_root.as_posix(),
                    "Source": "/host/project/data",
                }
            ]
        }
    )

    volume = cache.docker_volume(settings, client)

    assert cache.task_path == tmp_path / "data/cache/models"
    assert cache.task_path.is_dir()
    assert volume == {
        "/host/project/data/cache/models": {"bind": "/cache/models", "mode": "rw"}
    }
    assert cache.worker_environment == {
        "HF_HOME": "/cache/models/huggingface",
        "HF_HUB_CACHE": "/cache/models/huggingface/hub",
        "TORCH_HOME": "/cache/models/torch",
    }
