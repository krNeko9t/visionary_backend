from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.jobs import Artifact, JobSpec
from ..domain.mesh_formats import (
    EXPORT_MESH_FORMATS,
    MESH_ARTIFACT_IDS,
    get_mesh_formats,
)
from ..jobs.paths import JobPaths

FORMAT_MIME = {
    "obj": "model/obj",
    "glb": "model/gltf-binary",
}

FORMAT_LABEL = {
    "obj": "OBJ",
    "glb": "GLB",
}


@dataclass(frozen=True)
class MeshExportResult:
    artifacts: list[Artifact]
    error: str | None = None


def export_mesh_artifacts(
    spec: JobSpec,
    paths: JobPaths,
    artifacts: list[Artifact],
) -> MeshExportResult:
    requested_formats = [fmt for fmt in get_mesh_formats(spec) if fmt in EXPORT_MESH_FORMATS]
    if not requested_formats:
        return MeshExportResult(artifacts=[])

    try:
        import trimesh
    except ImportError as exc:
        return MeshExportResult(artifacts=[], error=f"mesh 格式转换依赖缺失: {exc}")

    derived: list[Artifact] = []
    for artifact in artifacts:
        if artifact.id not in MESH_ARTIFACT_IDS:
            continue
        if artifact.type != "ply":
            continue

        source_path = paths.resolve(artifact.path)
        if not source_path.is_file():
            return MeshExportResult(
                artifacts=[],
                error=f"mesh 源文件不存在: {artifact.path}",
            )

        try:
            mesh = trimesh.load(source_path, process=False)
        except Exception as exc:  # noqa: BLE001
            return MeshExportResult(
                artifacts=[],
                error=f"读取 mesh 失败 {artifact.path}: {exc}",
            )

        if not hasattr(mesh, "export"):
            return MeshExportResult(
                artifacts=[],
                error=f"无法转换 mesh 产物: {artifact.path}",
            )

        for fmt in requested_formats:
            output_path = source_path.with_name(f"{artifact.id}.{fmt}")
            try:
                mesh.export(output_path)
            except Exception as exc:  # noqa: BLE001
                return MeshExportResult(
                    artifacts=[],
                    error=f"导出 {fmt} 失败 {output_path.name}: {exc}",
                )

            derived.append(
                Artifact(
                    id=f"{artifact.id}_{fmt}",
                    stage_id=artifact.stage_id,
                    type=fmt,
                    path=str(output_path.relative_to(paths.root)),
                    mime=FORMAT_MIME[fmt],
                    label=f"{artifact.label or artifact.id} {FORMAT_LABEL[fmt]}",
                    metadata={
                        "source_artifact_id": artifact.id,
                        "format": fmt,
                    },
                )
            )

    return MeshExportResult(artifacts=derived)
