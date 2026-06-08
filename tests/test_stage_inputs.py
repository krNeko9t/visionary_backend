from pathlib import Path

from visionary_tasks.domain.jobs import JobSpec, JobState
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.jobs.storage import write_job_state
from visionary_tasks.services.ingest import ingest_job_files
from visionary_tasks.settings import Settings
from visionary_tasks.stages.inputs import missing_3dgs_to_pc_inputs
from visionary_tasks.jobs.ply_validation import validate_native_3dgs_ply


def _minimal_ply_header() -> bytes:
    content = (
        "ply\nformat ascii 1.0\nelement vertex 1\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property float opacity\nproperty float f_dc_0\nproperty float f_dc_1\n"
        "property float f_dc_2\nproperty float f_rest_0\nproperty float scale_0\n"
        "property float rot_0\nend_header\n0 0 0 1 0 0 0 0 0 0 0\n"
    )
    validate_native_3dgs_ply(content.encode("utf-8"))
    return content.encode("utf-8")


def _settings(tmp_path: Path) -> Settings:
    from visionary_tasks.settings import CorsSettings

    return Settings(
        data_root=tmp_path,
        jobs_root=tmp_path / "jobs",
        gs_repo_path=tmp_path / "gs",
        task_server_container_name="visionary-task-server",
        cors=CorsSettings(
            allow_origins=("http://localhost:5173",),
            allow_credentials=True,
            allow_methods=("GET", "POST"),
            allow_headers=("*",),
        ),
    )


def test_missing_3dgs_to_pc_inputs_ply_mode(tmp_path: Path):
    settings = _settings(tmp_path)
    paths = JobPaths(job_id="job1", root=settings.jobs_root / "job1")
    paths.ensure_layout()
    spec = JobSpec(
        outputs=["mesh"],
        options={"input_mode": "native_3dgs_ply", "iteration": 500},
    )
    ingest_job_files(spec, [("point_cloud.ply", _minimal_ply_header())], paths, "output")
    state = JobState(
        job_id="job1",
        spec=spec,
        status="queued",
        stages=[],
        artifacts=[],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        planned_stages=["3dgs-to-pc"],
    )
    write_job_state(paths.job_state_file, state)
    assert missing_3dgs_to_pc_inputs(paths, settings) == []
