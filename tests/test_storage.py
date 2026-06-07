from pathlib import Path

from visionary_tasks.domain.jobs import Artifact, JobSpec, JobState
from visionary_tasks.jobs.storage import (
    read_job_state,
    read_progress_events,
    read_worker_result,
    write_job_state,
    write_worker_result,
)
from visionary_tasks.workers.contract import WorkerResult


def test_job_state_roundtrip(tmp_path: Path):
    state = JobState(
        job_id="job1",
        spec=JobSpec(outputs=["point_cloud"]),
        status="queued",
        stages=[],
        artifacts=[],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        planned_stages=["colmap", "3dgs"],
    )
    path = tmp_path / "job.json"
    write_job_state(path, state)
    loaded = read_job_state(path)
    assert loaded is not None
    assert loaded.job_id == "job1"
    assert loaded.spec.outputs == ["point_cloud"]


def test_worker_result_roundtrip(tmp_path: Path):
    result = WorkerResult(
        stage_id="3dgs",
        status="done",
        artifacts=[
            Artifact(
                id="point_cloud",
                stage_id="3dgs",
                type="ply",
                path="output/point_cloud/iteration_500/point_cloud.ply",
            )
        ],
    )
    path = tmp_path / "result.json"
    write_worker_result(path, result)
    loaded = read_worker_result(path)
    assert loaded is not None
    assert loaded.artifacts[0].id == "point_cloud"


def test_progress_events_empty_when_missing(tmp_path: Path):
    assert read_progress_events(tmp_path / "missing.jsonl") == []
