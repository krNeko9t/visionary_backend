from __future__ import annotations

from .jobs import JobSpec

SUPPORTED_MESH_FORMATS: frozenset[str] = frozenset({"ply", "obj", "glb"})
DEFAULT_MESH_FORMATS: tuple[str, ...] = ("ply",)
MESH_ARTIFACT_IDS: frozenset[str] = frozenset({"mesh", "mesh_textured"})
EXPORT_MESH_FORMATS: frozenset[str] = frozenset({"obj", "glb"})


def get_mesh_formats(spec: JobSpec) -> tuple[str, ...]:
    raw = spec.options.get("mesh_formats")
    if raw is None:
        return DEFAULT_MESH_FORMATS
    if not isinstance(raw, list) or not raw:
        raise ValueError("options.mesh_formats 必须是非空列表")
    formats: list[str] = []
    for item in raw:
        fmt = str(item).strip().lower()
        if fmt not in SUPPORTED_MESH_FORMATS:
            supported = ", ".join(sorted(SUPPORTED_MESH_FORMATS))
            raise ValueError(f"不支持的 mesh 格式: {item}，可选: {supported}")
        if fmt not in formats:
            formats.append(fmt)
    return tuple(formats)


def validate_mesh_export_options(spec: JobSpec) -> None:
    if "mesh_formats" not in spec.options:
        return
    if "mesh" not in spec.outputs:
        raise ValueError("mesh_formats 仅能在 outputs 包含 mesh 时使用")
    get_mesh_formats(spec)


def needs_mesh_export(spec: JobSpec) -> bool:
    if "mesh" not in spec.outputs:
        return False
    return any(fmt in EXPORT_MESH_FORMATS for fmt in get_mesh_formats(spec))
