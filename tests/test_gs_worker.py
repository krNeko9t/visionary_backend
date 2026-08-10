from pathlib import Path
from unittest.mock import MagicMock

from visionary_tasks.config.loader import materialize_stage_config
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.settings import CorsSettings, Settings
from visionary_tasks.settings.gs import GsJobConfig
from visionary_tasks.stages import gs


def _settings(tmp_path: Path) -> Settings:
    return Settings(
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


def test_gs_config_uses_worker_image_and_container_paths(tmp_path: Path):
    paths = JobPaths(job_id="gs-config", root=tmp_path / "gs-config")
    paths.root.mkdir(parents=True)
    config = materialize_stage_config("3dgs", paths)

    assert isinstance(config, GsJobConfig)
    assert config.worker_image == "visionary-3dgs-worker:local"
    command = config.to_train_command("/job/colmap", "/job/output")
    assert command[:6] == [
        "python",
        "train.py",
        "-s",
        "/job/colmap",
        "-m",
        "/job/output",
    ]


def test_gs_stage_runs_as_docker_worker(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path)
    paths = JobPaths(job_id="gs-docker", root=settings.jobs_root / "gs-docker")
    paths.ensure_layout()
    (paths.colmap_dir / "sparse").mkdir(parents=True)
    config = materialize_stage_config(
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

    docker_client = MagicMock()
    docker_client.containers.get.return_value = MagicMock(
        attrs={
            "Mounts": [
                {
                    "Destination": tmp_path.as_posix(),
                    "Source": "/host/data",
                }
            ]
        }
    )
    monkeypatch.setattr(gs.docker, "from_env", lambda: docker_client)

    captured: dict[str, object] = {}

    def fake_run_docker_worker(**kwargs):
        captured.update(kwargs)
        ply = paths.gs_output_ply(config.output_relative, config.output_iteration)
        ply.parent.mkdir(parents=True)
        ply.write_bytes(b"ply")
        return "worker logs"

    monkeypatch.setattr(gs, "run_docker_worker", fake_run_docker_worker)

    result = gs.run(settings, paths)

    assert result.status == "done"
    assert result.logs == "worker logs"
    assert captured["image"] == "visionary-3dgs-worker:local"
    assert captured["volumes"] == {
        "/host/data/jobs/gs-docker": {"bind": "/job", "mode": "rw"}
    }
    command = captured["command"]
    assert isinstance(command, list)
    assert command[:6] == [
        "python",
        "train.py",
        "-s",
        "/job/colmap",
        "-m",
        "/job/output",
    ]
    docker_client.close.assert_called_once_with()
