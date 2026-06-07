from pathlib import Path

from visionary_tasks.domain.jobs import JobSpec, JobState, StageState
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.jobs.storage import append_progress_event, write_job_state
from visionary_tasks.services.progress import compute_job_progress, derive_job_status
from visionary_tasks.workers.contract import make_progress_event


def test_derive_job_status_done(tmp_path):
    state = JobState(
        job_id="abc",
        spec=JobSpec(outputs=["point_cloud"]),
        status="queued",
        stages=[
            StageState(stage_id="colmap", status="done", progress=1.0),
            StageState(stage_id="3dgs", status="done", progress=1.0),
        ],
        artifacts=[],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        planned_stages=["colmap", "3dgs"],
    )
    assert derive_job_status(state) == "done"


def test_compute_job_progress_with_events(tmp_path):
    job_root = tmp_path / "job1"
    paths = JobPaths(job_id="job1", root=job_root)
    paths.ensure_layout()

    state = JobState(
        job_id="job1",
        spec=JobSpec(outputs=["point_cloud"]),
        status="running",
        stages=[
            StageState(stage_id="colmap", status="done", progress=1.0),
            StageState(stage_id="3dgs", status="running", progress=0.0),
        ],
        artifacts=[],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        planned_stages=["colmap", "3dgs"],
    )
    write_job_state(paths.job_state_file, state)

    append_progress_event(
        paths.stage_events_file("3dgs"),
        make_progress_event("3dgs", progress=0.5, message="halfway"),
    )

    progress = compute_job_progress(state, paths)
    assert 20.0 < progress < 80.0
