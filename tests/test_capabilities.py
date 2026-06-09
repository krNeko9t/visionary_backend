from visionary_tasks.services.job_service import JobService


def test_capabilities_exposes_mesh_formats():
    payload = JobService.capabilities()
    assert payload["mesh_formats"] == ["glb", "obj", "ply"]


def test_capabilities_exposes_stage_presets_from_config_dirs():
    payload = JobService.capabilities()
    assert set(payload["stage_presets"]["colmap"]) == {"general", "video", "fast", "fisheye"}
    assert set(payload["stage_presets"]["3dgs"]) == {"small", "mid", "high"}
    assert set(payload["stage_presets"]["gaussian-wrapping"]) == {
        "high_geo",
        "high_geo_tex",
        "simple",
    }
