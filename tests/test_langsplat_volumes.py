from pathlib import Path
from unittest.mock import MagicMock

from visionary_tasks.config.loader import materialize_stage_config
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.settings import CorsSettings, Settings
from visionary_tasks.stages import langsplat
from visionary_tasks.workers.adapters.langsplat import build_langsplat_live_code_volumes


def test_build_langsplat_live_code_volumes(tmp_path: Path):
    repo = tmp_path / "LangSplatV2"
    (repo / "scene").mkdir(parents=True)
    (repo / "train.py").write_text("print('train')\n", encoding="utf-8")

    volumes = build_langsplat_live_code_volumes(repo)

    assert str(repo / "train.py") in volumes
    assert volumes[str(repo / "train.py")]["bind"] == "/workspace/train.py"
    assert str(repo / "scene") in volumes
    assert volumes[str(repo / "scene")]["mode"] == "ro"


def test_langsplat_stage_shares_writable_model_cache(tmp_path: Path, monkeypatch):
    settings = Settings(
        data_root=tmp_path,
        jobs_root=tmp_path / "jobs",
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
    paths = JobPaths(job_id="langsplat-cache", root=settings.jobs_root / "langsplat-cache")
    paths.ensure_layout()
    (paths.colmap_dir / "sparse").mkdir(parents=True)
    settings.ckpts_root.mkdir(parents=True)
    (settings.ckpts_root / "sam_vit_h_4b8939.pth").write_bytes(b"sam")

    gs_config = materialize_stage_config(
        "3dgs",
        paths,
        override={
            "training": {
                "output_iteration": 1,
                "save_iterations": [1],
                "checkpoint_iterations": [1],
            }
        },
    )
    checkpoint = paths.gs_checkpoint(gs_config.output_relative, gs_config.output_iteration)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"checkpoint")
    config = materialize_stage_config(
        "langsplat",
        paths,
        override={
            "model": {"feature_levels": [0]},
            "training": {"checkpoint_iterations": [1]},
            "export": {"checkpoint": 1, "levels": [0]},
        },
    )

    docker_client = MagicMock()
    docker_client.containers.get.return_value = MagicMock(
        attrs={
            "Mounts": [
                {"Destination": tmp_path.as_posix(), "Source": "/host/data"},
                {
                    "Destination": settings.ckpts_root.as_posix(),
                    "Source": "/host/ckpts",
                },
            ]
        }
    )
    monkeypatch.setattr(langsplat.docker, "from_env", lambda: docker_client)

    calls: list[dict[str, object]] = []

    def fake_run_docker_worker(**kwargs):
        calls.append(kwargs)
        label = str(kwargs["label"])
        if label.startswith("langsplat train"):
            model_dir = paths.langsplat_model_dir(config.runtime.model_relative, 0)
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "chkpnt1.pth").write_bytes(b"model")
        elif label == "langsplat export":
            export_root = paths.langsplat_export_root(config.export.output_relative, 1)
            export_root.mkdir(parents=True, exist_ok=True)
            (export_root / "queries.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(langsplat, "run_docker_worker", fake_run_docker_worker)

    result = langsplat.run(settings, paths)

    assert result.status == "done"
    assert len(calls) == 3
    for call in calls:
        assert call["volumes"]["/host/data/cache/models"] == {
            "bind": "/cache/models",
            "mode": "rw",
        }
        assert call["volumes"]["/host/ckpts"] == {
            "bind": settings.ckpts_root.as_posix(),
            "mode": "ro",
        }
        assert call["environment"] == {
            "HF_HOME": "/cache/models/huggingface",
            "HF_HUB_CACHE": "/cache/models/huggingface/hub",
            "TORCH_HOME": "/cache/models/torch",
        }
