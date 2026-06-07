from visionary_tasks.api.v1.schemas import JobSpecRequest, JobStatusResponse
from visionary_tasks.domain.jobs import Artifact, JobSpec, JobState, StageState


def test_job_spec_request_to_domain():
    spec = JobSpecRequest(
        outputs=["mesh"],
        preset="standard",
        options={"language_features": False},
    ).to_domain()
    assert spec.outputs == ["mesh"]
    assert spec.preset == "standard"


def test_job_status_response_from_state():
    state = JobState(
        job_id="job1",
        spec=JobSpec(outputs=["point_cloud"]),
        status="running",
        stages=[StageState(stage_id="colmap", status="running")],
        artifacts=[
            Artifact(
                id="point_cloud",
                stage_id="3dgs",
                type="ply",
                path="output/point_cloud/iteration_500/point_cloud.ply",
            )
        ],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        progress=12.5,
        current_stage_id="colmap",
        planned_stages=["colmap", "3dgs"],
    )
    response = JobStatusResponse.from_state(state)
    assert response.job_id == "job1"
    assert response.progress == 12.5
    assert response.artifacts[0].id == "point_cloud"
