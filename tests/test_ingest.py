from pathlib import Path

import pytest

from visionary_tasks.domain.jobs import JobSpec
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.jobs.ply_validation import validate_native_3dgs_ply
from visionary_tasks.services.ingest import ingest_job_files


def _minimal_ply_header() -> bytes:
    lines = [
        "ply",
        "format ascii 1.0",
        "element vertex 1",
        "property float x",
        "property float y",
        "property float z",
        "property float opacity",
        "property float f_dc_0",
        "property float f_dc_1",
        "property float f_dc_2",
        "property float f_rest_0",
        "property float scale_0",
        "property float rot_0",
        "end_header",
        "0 0 0 1 0 0 0 0 0 0 0",
    ]
    return "\n".join(lines).encode("utf-8")


def test_validate_native_3dgs_ply_accepts_minimal_header():
    validate_native_3dgs_ply(_minimal_ply_header())


def test_validate_native_3dgs_ply_rejects_missing_fields():
    with pytest.raises(ValueError, match="缺少必要字段"):
        validate_native_3dgs_ply(b"ply\nformat ascii 1.0\nend_header\n")


def test_ingest_native_ply_places_file_at_iteration_path(tmp_path: Path):
    paths = JobPaths(job_id="job1", root=tmp_path / "job1")
    paths.ensure_layout()
    spec = JobSpec(
        outputs=["mesh"],
        options={"input_mode": "native_3dgs_ply", "iteration": 1234},
    )
    ingest_job_files(spec, [("point_cloud.ply", _minimal_ply_header())], paths, "output")
    ply_path = paths.gs_output_ply("output", 1234)
    assert ply_path.exists()
    assert (paths.output_dir("output") / "cfg_args").exists()
