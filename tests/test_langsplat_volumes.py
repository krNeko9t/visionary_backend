import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from visionary_progress import ProgressReporter

from visionary_tasks.api.v1.schemas import JobStatusResponse
from visionary_tasks.config.loader import materialize_stage_config
from visionary_tasks.domain.jobs import JobSpec, JobState, StageState
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.jobs.storage import write_job_state
from visionary_tasks.services.job_service import JobService
from visionary_tasks.settings import CorsSettings, Settings
from visionary_tasks.stages import langsplat


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path,
        jobs_root=tmp_path / "jobs",
        ckpts_root=tmp_path / "ckpts",
        task_server_container_name="visionary-task-server",
        cors=CorsSettings(
            allow_origins=("http://localhost:5173",),
            allow_credentials=False,
            allow_methods=("GET", "POST"),
            allow_headers=("*",),
        ),
    )


@pytest.mark.parametrize("feature_levels", [[0], [3, 1]])
@pytest.mark.parametrize("missing_output", [None, "model", "export"])
def test_langsplat_stage_shares_writable_model_cache(
    tmp_path: Path, monkeypatch, feature_levels: list[int], missing_output
):
    settings = _settings(tmp_path)
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
            "model": {"feature_levels": feature_levels},
            "training": {"checkpoint_iterations": [1]},
            "export": {"checkpoint": 1, "levels": feature_levels},
        },
    )
    state = JobState(
        job_id=paths.job_id, spec=JobSpec(outputs=["language_model"]), status="running",
        stages=[StageState("colmap", "done"), StageState("3dgs", "done"), StageState("langsplat", "running")],
        artifacts=[], created_at="2026-01-01T00:00:00+00:00", updated_at="2026-01-01T00:00:00+00:00",
        planned_stages=["colmap", "3dgs", "langsplat"],
    )
    write_job_state(paths.job_state_file, state)
    service = JobService(settings)

    def query():
        return JobStatusResponse.from_state(service.get_job(paths.job_id))

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
    observed_starts = []
    observed_iterations = []
    observed_preprocessing = []

    def fake_run_docker_worker(**kwargs):
        calls.append(kwargs)
        label = str(kwargs["label"])
        initial = query().stages[-1]
        observed_starts.append(initial)
        with monkeypatch.context() as environment:
            for key, value in kwargs["environment"].items():
                environment.setenv(key, value)
            environment.setenv("VISIONARY_PROGRESS_FILE", str(paths.stage_events_file("langsplat")))
            reporter = ProgressReporter.from_env()
        assert initial.current_step.id == reporter.step_id
        if label == "langsplat preprocess":
            reporter.record(event_type="step_started", message="加载 OpenCLIP 模型")
            for completed in (0, 1, 2):
                reporter.record(completed=completed, total=2, unit="image", message="逐图提取语言特征")
                observed_preprocessing.append(query())
            reporter.record(message="写入语言特征")
            observed_preprocessing.append(query())
            reporter.record(event_type="step_completed", progress=1.0, message="预处理完成")
        elif label.startswith("langsplat train"):
            feature_level = int(label.rsplit("L", 1)[1])
            reporter.record(event_type="step_started", message="加载场景与训练检查点")
            for iteration in (250, 500, 1000):
                reporter.record(completed=iteration, total=1000, unit="iteration", message="训练中")
                observed_iterations.append(query())
            reporter.record(event_type="step_completed", progress=1.0, message="训练完成")
            if missing_output == "model":
                return
            model_dir = paths.langsplat_model_dir(config.runtime.model_relative, feature_level)
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "chkpnt1.pth").write_bytes(b"model")
        elif label == "langsplat export":
            if missing_output == "export":
                return
            export_root = paths.langsplat_export_root(config.export.output_relative, 1)
            export_root.mkdir(parents=True, exist_ok=True)
            (export_root / "queries.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(langsplat, "run_docker_worker", fake_run_docker_worker)

    result = langsplat.run(settings, paths)

    if missing_output:
        assert result.status == "error"
        assert "目录为空" in result.error
        assert query().status == "running"  # Only the runner may finalize the stage.
        return
    assert result.status == "done"
    assert query().stages[-1].progress == 1.0
    assert query().status == "running"
    assert observed_starts[0].current_step.id == {"name": "preprocess"}
    assert observed_starts[1].progress == pytest.approx(0.3)
    assert observed_starts[-1].progress == pytest.approx(0.8)
    assert observed_starts[-1].current_step.id == {"name": "export"}
    assert [body.stages[-1].current_step.completed for body in observed_preprocessing] == [0, 1, 2, 2]
    assert [body.stages[-1].progress for body in observed_preprocessing] == pytest.approx([0.0, 0.15, 0.3, 0.3])
    assert observed_preprocessing[1].progress == pytest.approx(86.5789473684)
    for initial in observed_starts:
        assert initial.current_step.completed is None
        assert initial.current_step.total is None
        assert initial.current_step.unit is None
    assert [body.stages[-1].current_step.completed for body in observed_iterations] == [250, 500, 1000] * len(feature_levels)
    assert all(a.progress <= b.progress for a, b in zip(observed_iterations, observed_iterations[1:]))
    if len(feature_levels) == 1:
        assert observed_iterations[1].stages[-1].progress == pytest.approx(0.55)
        assert observed_iterations[1].progress == pytest.approx(92.8947368421)
    assert len(calls) == len(feature_levels) + 2
    train_calls = [call for call in calls if str(call["label"]).startswith("langsplat train")]
    for index, call in enumerate(train_calls):
        command = call["command"]
        assert isinstance(command, list)
        assert "--progress_offset" not in command and "--progress_span" not in command
        environment = call["environment"]
        assert environment["VISIONARY_PROGRESS_FILE"] == "/job/events/langsplat.jsonl"
        assert json.loads(environment["VISIONARY_PROGRESS_STEP"]) == {
            "name": "train", "level": feature_levels[index],
        }
    for call in calls:
        assert call["volumes"][str(Path("/host/data") / "cache" / "models")] == {
            "bind": "/cache/models",
            "mode": "rw",
        }
        assert call["volumes"][str(Path("/host/ckpts"))] == {
            "bind": settings.ckpts_root.as_posix(),
            "mode": "ro",
        }
        assert {key: call["environment"][key] for key in ("HF_HOME", "HF_HUB_CACHE", "TORCH_HOME")} == {
            "HF_HOME": "/cache/models/huggingface",
            "HF_HUB_CACHE": "/cache/models/huggingface/hub",
            "TORCH_HOME": "/cache/models/torch",
        }
        assert "/workspace/preprocess.py" not in [
            bind["bind"] for bind in call["volumes"].values()
        ]
