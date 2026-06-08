import pytest

trimesh = pytest.importorskip("trimesh")

from pathlib import Path

from visionary_tasks.domain.jobs import Artifact, JobSpec
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.services.mesh_export import export_mesh_artifacts


def _write_triangle_ply(path: Path) -> None:
    mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
    )
    mesh.export(path)


def test_export_mesh_obj_and_glb(tmp_path):
    root = tmp_path / "job1"
    output_dir = root / "output"
    output_dir.mkdir(parents=True)
    ply_path = output_dir / "mesh_poisson.ply"
    _write_triangle_ply(ply_path)

    paths = JobPaths(job_id="job1", root=root)
    spec = JobSpec(
        outputs=["mesh"],
        options={"mesh_formats": ["ply", "obj", "glb"]},
    )
    source = Artifact(
        id="mesh",
        stage_id="3dgs-to-pc",
        type="ply",
        path="output/mesh_poisson.ply",
        label="Mesh",
    )

    result = export_mesh_artifacts(spec, paths, [source])

    assert result.error is None
    assert {artifact.id for artifact in result.artifacts} == {"mesh_obj", "mesh_glb"}
    assert (output_dir / "mesh.obj").is_file()
    assert (output_dir / "mesh.glb").is_file()

    obj_artifact = next(item for item in result.artifacts if item.id == "mesh_obj")
    glb_artifact = next(item for item in result.artifacts if item.id == "mesh_glb")
    assert obj_artifact.type == "obj"
    assert glb_artifact.type == "glb"
    assert obj_artifact.mime == "model/obj"
    assert glb_artifact.mime == "model/gltf-binary"
    assert obj_artifact.metadata["source_artifact_id"] == "mesh"


def test_export_mesh_textured_derived_artifacts(tmp_path):
    root = tmp_path / "job1"
    output_dir = root / "output"
    output_dir.mkdir(parents=True)
    _write_triangle_ply(output_dir / "mesh_ours.ply")
    _write_triangle_ply(output_dir / "mesh_textured.ply")

    paths = JobPaths(job_id="job1", root=root)
    spec = JobSpec(
        outputs=["mesh"],
        options={"mesh_formats": ["obj"]},
    )
    artifacts = [
        Artifact(id="mesh", stage_id="gaussian-wrapping", type="ply", path="output/mesh_ours.ply"),
        Artifact(
            id="mesh_textured",
            stage_id="gaussian-wrapping",
            type="ply",
            path="output/mesh_textured.ply",
        ),
    ]

    result = export_mesh_artifacts(spec, paths, artifacts)

    assert result.error is None
    assert {artifact.id for artifact in result.artifacts} == {"mesh_obj", "mesh_textured_obj"}


def test_export_skips_when_only_ply_requested(tmp_path):
    root = tmp_path / "job1"
    paths = JobPaths(job_id="job1", root=root)
    spec = JobSpec(outputs=["mesh"])
    source = Artifact(id="mesh", stage_id="3dgs-to-pc", type="ply", path="output/mesh.ply")

    result = export_mesh_artifacts(spec, paths, [source])

    assert result.error is None
    assert result.artifacts == []
