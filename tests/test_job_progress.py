"""Progress is observed through the existing HTTP job interface."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from visionary_tasks.api.v1 import routes
from visionary_tasks.config.loader import materialize_stage_config
from visionary_tasks.domain.jobs import JobSpec, JobState, StageState
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.jobs.storage import write_job_state
from visionary_tasks.settings import CorsSettings, Settings


@pytest.fixture
def progress_job(tmp_path, monkeypatch):
    settings = Settings(
        data_root=tmp_path,
        jobs_root=tmp_path / "jobs",
        ckpts_root=tmp_path / "ckpts",
        task_server_container_name="visionary-task-server",
        cors=CorsSettings((), False, ("GET", "POST"), ("*",)),
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        def create(levels=(2,)):
            paths = JobPaths.from_settings(settings, "progress-job")
            paths.ensure_layout()
            materialize_stage_config("langsplat", paths, override={
                "model": {"feature_levels": list(levels)},
            })
            state = JobState(
                job_id=paths.job_id,
                spec=JobSpec(outputs=["language_model"]),
                status="running",
                stages=[
                    StageState("colmap", "done", progress=1.0),
                    StageState("3dgs", "done", progress=1.0),
                    StageState("langsplat", "running"),
                ],
                artifacts=[],
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
                planned_stages=["colmap", "3dgs", "langsplat"],
            )
            write_job_state(paths.job_state_file, state)
            return client, paths, state
        yield create


def test_training_counts_update_one_consistent_job_view(progress_job):
    from visionary_progress import CurrentStep, record_progress

    client, paths, _ = progress_job()
    event_file = paths.stage_events_file("langsplat")
    record_progress(event_file, "langsplat", progress=0.3, message="预处理完成")
    responses = []
    for completed in (250, 500):
        record_progress(event_file, "langsplat", current_step=CurrentStep(
            id={"name": "train", "level": 2}, label="训练 level=2",
            completed=completed, total=1000, unit="iteration", message="训练中",
        ))
        response = client.get(f"/api/v1/jobs/{paths.job_id}")
        assert response.status_code == 200
        responses.append(response.json())

    first, second = responses
    assert first["stages"][-1]["progress"] == pytest.approx(0.425)
    assert second["stages"][-1]["progress"] == pytest.approx(0.55)
    assert first["progress"] < second["progress"]
    assert second["progress"] == pytest.approx(92.8947368421)
    assert second["status"] == "running"
    step = second["stages"][-1]["current_step"]
    assert step == {
        "id": {"name": "train", "level": 2}, "label": "训练 level=2",
        "progress": 0.5, "completed": 500, "total": 1000,
        "unit": "iteration", "message": "训练中",
    }
    assert client.get(f"/api/v1/jobs/{paths.job_id}").json() == second
    events = client.get(f"/api/v1/jobs/{paths.job_id}/events").json()["events"]
    assert events[-1]["progress"] == pytest.approx(0.55)
    assert events[-1]["iteration"] == 500
    assert events[-1]["total_iterations"] == 1000
    assert events[-1]["current_step"] == step


def test_switching_levels_keeps_completed_share_and_clears_details(progress_job):
    from visionary_progress import CurrentStep, record_progress

    client, paths, _ = progress_job(levels=(3, 1))
    event_file = paths.stage_events_file("langsplat")
    url = f"/api/v1/jobs/{paths.job_id}"
    record_progress(event_file, "langsplat", progress=0.3)
    record_progress(event_file, "langsplat", current_step=CurrentStep(
        id={"name": "train", "level": 3}, completed=1000, total=1000, unit="iteration",
    ))
    completed = client.get(url).json()
    assert completed["stages"][-1]["progress"] == pytest.approx(0.55)
    record_progress(event_file, "langsplat", current_step=CurrentStep(
        id={"name": "train", "level": 1}, message="加载模型",
    ))
    switched = client.get(url).json()
    step = switched["stages"][-1]["current_step"]
    assert switched["progress"] == completed["progress"]
    assert step["id"] == {"name": "train", "level": 1}
    assert step["label"] == "训练 level=1"
    assert step["completed"] is None and step["total"] is None and step["unit"] is None
    record_progress(event_file, "langsplat", current_step=CurrentStep(
        id={"name": "train", "level": 1}, completed=250, total=1000, unit="iteration",
    ))
    record_progress(event_file, "langsplat", message="保存检查点")
    halfway = client.get(url).json()
    step = halfway["stages"][-1]["current_step"]
    assert halfway["stages"][-1]["progress"] == pytest.approx(0.6125)
    assert step["progress"] == 0.25 and step["completed"] == 250
    assert step["message"] == "保存检查点"
    # An explicit local completion supersedes stale partial counts.
    record_progress(event_file, "langsplat", current_step=CurrentStep(
        id={"name": "train", "level": 1}, progress=1.0, message="训练完成",
    ))
    final = client.get(url).json()
    assert final["stages"][-1]["progress"] == pytest.approx(0.8)
    assert final["stages"][-1]["current_step"]["completed"] is None
    assert final["status"] == "running"


@pytest.mark.parametrize("fields", [
    {"completed": -1}, {"total": 0}, {"total": -1},
    {"progress": 1.1}, {"progress": float("nan")}, {"completed": float("inf")},
    {"completed": 250, "total": 1000, "progress": 0.5},
])
def test_invalid_local_counts_leave_the_job_queryable(progress_job, fields):
    from visionary_progress import CurrentStep, record_progress

    client, paths, _ = progress_job()
    url = f"/api/v1/jobs/{paths.job_id}"
    before = client.get(url).json()
    with pytest.raises(ValueError):
        record_progress(paths.stage_events_file("langsplat"), "langsplat", current_step=CurrentStep(
            id={"name": "train", "level": 2}, **fields,
        ))
    assert client.get(url).json() == before


def test_partial_counts_and_message_only_updates_keep_local_progress(progress_job):
    from visionary_progress import CurrentStep, record_progress

    client, paths, _ = progress_job()
    event_file = paths.stage_events_file("langsplat")
    url = f"/api/v1/jobs/{paths.job_id}"
    record_progress(event_file, "langsplat", progress=0.3)
    for fields in (
        {"progress": 0.25},
        {"message": "加载特征"},
        {"completed": 250},
    ):
        record_progress(event_file, "langsplat", current_step=CurrentStep(
            id={"name": "train", "level": 2}, **fields,
        ))
        body = client.get(url).json()
        assert body["stages"][-1]["progress"] == pytest.approx(0.425)
        assert body["stages"][-1]["current_step"]["progress"] == 0.25
    record_progress(event_file, "langsplat", current_step=CurrentStep(
        id={"name": "train", "level": 2}, completed=1200, total=1000, unit="iteration",
    ))
    step = client.get(url).json()["stages"][-1]["current_step"]
    assert step["progress"] == 1.0 and step["completed"] == 1200


def test_old_training_events_and_unfinished_utf8_tail_are_read_incrementally(progress_job):
    import json

    client, paths, _ = progress_job()
    event_file = paths.stage_events_file("langsplat")
    url = f"/api/v1/jobs/{paths.job_id}"
    old = {
        "stage_id": "langsplat", "event_type": "progress", "progress": 0.425,
        "iteration": 250, "total_iterations": 1000,
        "message": "LangSplat 训练中 level=2 iteration=250/1000",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    event_file.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
    first = client.get(url).json()
    assert first["stages"][-1]["progress"] == pytest.approx(0.425)
    assert first["stages"][-1]["current_step"]["completed"] == 250
    old.update(progress=0.55, iteration=500, message="LangSplat 训练中 level=2 iteration=500/1000")
    tail = (json.dumps(old, ensure_ascii=False) + "\n").encode()
    split = tail.index("训".encode()) + 1
    with event_file.open("ab") as stream:
        stream.write(tail[:split])
    assert client.get(url).json() == first
    assert len(client.get(url + "/events").json()["events"]) == 1
    with event_file.open("ab") as stream:
        stream.write(tail[split:])
    last = client.get(url).json()
    assert last["stages"][-1]["progress"] == pytest.approx(0.55)
    assert last["stages"][-1]["current_step"]["completed"] == 500
    assert client.get(url).json() == last


def test_historical_state_and_milestones_without_details_remain_readable(progress_job):
    import json

    client, paths, state = progress_job()
    payload = state.to_dict()
    for stage in payload["stages"]:
        stage.pop("current_step")
        stage.pop("progress_steps")
    paths.job_state_file.write_text(json.dumps(payload))
    paths.stage_config_path("langsplat").unlink()
    paths.stage_events_file("langsplat").write_text(json.dumps({
        "stage_id": "langsplat", "event_type": "progress", "progress": 0.3,
        "message": "LangSplat preprocess 完成", "timestamp": state.created_at,
    }) + "\n")
    response = client.get(f"/api/v1/jobs/{paths.job_id}")
    assert response.status_code == 200
    stage = response.json()["stages"][-1]
    assert stage["progress"] == 0.3 and stage["current_step"] is None


@pytest.mark.parametrize("status, expected_total, expected_stage", [
    ("running", 99.0, 1.0), ("done", 100.0, 1.0),
    ("error", 99.0, 1.0), ("cancelled", 0.0, 1.0),
])
def test_lifecycle_wins_over_completed_local_work(progress_job, status, expected_total, expected_stage):
    from visionary_progress import record_progress

    client, paths, state = progress_job()
    record_progress(paths.stage_events_file("langsplat"), "langsplat", progress=1.0)
    state.status = status
    state.stages[-1].status = status if status != "cancelled" else "running"
    state.stages[-1].error = "产物检查失败" if status == "error" else None
    state.cancel_requested = status == "cancelled"
    write_job_state(paths.job_state_file, state)
    body = client.get(f"/api/v1/jobs/{paths.job_id}").json()
    assert body["status"] == status
    assert body["progress"] == expected_total
    assert body["stages"][-1]["progress"] == expected_stage
    if status == "error":
        assert body["error"] == body["message"] == "产物检查失败"


def test_successful_stage_overrides_last_partial_event(progress_job):
    from visionary_progress import record_progress

    client, paths, state = progress_job()
    record_progress(paths.stage_events_file("langsplat"), "langsplat", progress=0.4)
    state.stages[-1].status = "done"
    write_job_state(paths.job_state_file, state)
    body = client.get(f"/api/v1/jobs/{paths.job_id}").json()
    assert body["stages"][-1]["progress"] == 1.0
    assert body["progress"] == 100.0


def test_other_stage_internal_work_uses_the_same_query(progress_job):
    from visionary_progress import CurrentStep, StepDefinition, record_progress

    client, paths, state = progress_job()
    state.planned_stages = ["colmap"]
    state.stages = [StageState("colmap", "running", progress_steps=[
        StepDefinition({"name": "features"}, "提取特征", 0.4),
        StepDefinition({"name": "matching"}, "匹配", 0.6),
    ])]
    write_job_state(paths.job_state_file, state)
    record_progress(paths.stage_events_file("colmap"), "colmap", current_step=CurrentStep(
        id={"name": "features"}, completed=5, total=10, unit="image", message="处理图像",
    ))
    body = client.get(f"/api/v1/jobs/{paths.job_id}").json()
    assert body["progress"] == 20.0
    assert body["stages"][0]["progress"] == 0.2
    assert body["stages"][0]["current_step"] == {
        "id": {"name": "features"}, "label": "提取特征", "progress": 0.5,
        "completed": 5, "total": 10, "unit": "image", "message": "处理图像",
    }


def test_complete_last_json_record_is_read_before_its_newline(progress_job):
    import json

    client, paths, _ = progress_job()
    event_file = paths.stage_events_file("langsplat")
    event_file.write_bytes(json.dumps({
        "stage_id": "langsplat", "event_type": "progress", "progress": 0.3,
    }).encode())
    url = f"/api/v1/jobs/{paths.job_id}"
    body = client.get(url).json()
    assert body["stages"][-1]["progress"] == 0.3
    with event_file.open("ab") as stream:
        stream.write(b"\n")
    assert client.get(url).json() == body


@pytest.mark.parametrize("name, milestone, completed, total, expected", [
    ("preprocess", 0.0, 2, 4, 0.15), ("export", 0.8, 1, 2, 0.9),
])
def test_preprocess_and_export_work_use_the_shared_contract(progress_job, name, milestone, completed, total, expected):
    from visionary_progress import CurrentStep, record_progress

    client, paths, _ = progress_job()
    event_file = paths.stage_events_file("langsplat")
    record_progress(event_file, "langsplat", progress=milestone)
    record_progress(event_file, "langsplat", current_step=CurrentStep(
        id={"name": name}, completed=completed, total=total, unit="item", message="受控工作",
    ))
    url = f"/api/v1/jobs/{paths.job_id}"
    stage = client.get(url).json()["stages"][-1]
    assert stage["progress"] == pytest.approx(expected)
    assert stage["current_step"]["completed"] == completed
    assert stage["current_step"]["message"] == "受控工作"
    event = client.get(url + "/events").json()["events"][-1]
    assert event["progress"] == pytest.approx(expected)
    assert event["current_step"] == stage["current_step"]


def test_legacy_stage_counts_can_follow_generic_internal_iteration_work(progress_job):
    from visionary_progress import CurrentStep, StepDefinition, record_progress

    client, paths, state = progress_job()
    state.planned_stages = ["3dgs"]
    state.stages = [StageState("3dgs", "running", progress_steps=[
        StepDefinition({"name": "refine"}, "局部优化", 1.0),
    ])]
    write_job_state(paths.job_state_file, state)
    event_file = paths.stage_events_file("3dgs")
    record_progress(event_file, "3dgs", current_step=CurrentStep(
        id={"name": "refine"}, completed=2, total=10, unit="iteration",
    ))
    # The existing 3DGS completion milestone counts the whole stage, without a work identity.
    record_progress(event_file, "3dgs", event_type="completed", progress=1.0,
                    iteration=1000, total_iterations=1000, message="3DGS 训练完成")
    url = f"/api/v1/jobs/{paths.job_id}"
    body = client.get(url).json()
    assert body["stages"][0]["progress"] == 1.0
    assert body["status"] == "running"
    assert body["stages"][0]["current_step"]["completed"] == 2
    event = client.get(url + "/events").json()["events"][-1]
    assert event["progress"] == 1.0
    assert event["iteration"] == event["total_iterations"] == 1000
    assert event["current_step"] is None


def test_legacy_events_without_timestamps_have_a_stable_query_response(progress_job):
    client, paths, _ = progress_job()
    paths.stage_events_file("langsplat").write_text(
        '{"stage_id":"langsplat","event_type":"progress","progress":0.3}\n'
    )
    url = f"/api/v1/jobs/{paths.job_id}/events"
    assert client.get(url).json() == client.get(url).json()
