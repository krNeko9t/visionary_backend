from visionary_tasks.services.job_service import JobService


def test_capabilities_exposes_mesh_formats():
    payload = JobService.capabilities()
    assert payload["mesh_formats"] == ["glb", "obj", "ply"]
