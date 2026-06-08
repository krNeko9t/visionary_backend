from pathlib import Path

import pytest

from visionary_tasks.config.loader import materialize_stage_config, stage_presets_from_options, validate_stage_presets
from visionary_tasks.domain.jobs import JobSpec
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.services.job_service import JobService


def test_stage_presets_from_options():
    spec = JobSpec(
        outputs=["point_cloud"],
        options={"stage_presets": {"colmap": "video", "3dgs": "small"}},
    )
    assert stage_presets_from_options(spec.options) == {"colmap": "video", "3dgs": "small"}


def test_validate_stage_presets_rejects_unknown_preset():
    with pytest.raises(ValueError, match="未知 preset"):
        validate_stage_presets({"colmap": "unknown"})


def test_materialize_colmap_stage_with_preset(tmp_path: Path):
    job_id = "test-colmap-preset"
    paths = JobPaths(job_id=job_id, root=tmp_path / job_id)
    paths.root.mkdir(parents=True)

    config = materialize_stage_config("colmap", paths, preset="video")
    assert config.converter.matcher == "sequential"
    assert paths.stage_config_path("colmap").exists()


def test_capabilities_exposes_discovered_stage_presets():
    payload = JobService.capabilities()
    assert "colmap" in payload["stage_presets"]
    assert "3dgs" in payload["stage_presets"]
    assert "video" in payload["stage_presets"]["colmap"]
