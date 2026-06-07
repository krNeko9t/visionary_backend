from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputDefinition:
    id: str
    label: str
    required_stages: tuple[str, ...]


@dataclass(frozen=True)
class StageDefinition:
    id: str
    label: str
    order: int
    weight: float
    depends_on: tuple[str, ...]
    input_hints: tuple[str, ...]


@dataclass(frozen=True)
class PipelinePlan:
    outputs: tuple[str, ...]
    stages: tuple[str, ...]


OUTPUT_DEFINITIONS: dict[str, OutputDefinition] = {
    "point_cloud": OutputDefinition(
        id="point_cloud",
        label="3D Gaussian Point Cloud",
        required_stages=("colmap", "3dgs"),
    ),
    "mesh": OutputDefinition(
        id="mesh",
        label="Textured Mesh",
        required_stages=("colmap", "3dgs", "gaussian-wrapping"),
    ),
    "language_model": OutputDefinition(
        id="language_model",
        label="Language Feature Model",
        required_stages=("colmap", "3dgs", "langsplat"),
    ),
}

STAGE_DEFINITIONS: dict[str, StageDefinition] = {
    "colmap": StageDefinition(
        id="colmap",
        label="COLMAP",
        order=0,
        weight=0.2,
        depends_on=(),
        input_hints=("input/ 下有图像",),
    ),
    "3dgs": StageDefinition(
        id="3dgs",
        label="3DGS",
        order=1,
        weight=0.6,
        depends_on=("colmap",),
        input_hints=("colmap/sparse",),
    ),
    "langsplat": StageDefinition(
        id="langsplat",
        label="LangSplatV2",
        order=2,
        weight=0.15,
        depends_on=("colmap", "3dgs"),
        input_hints=("colmap/sparse", "output/chkpnt{N}.pth"),
    ),
    "gaussian-wrapping": StageDefinition(
        id="gaussian-wrapping",
        label="Mesh",
        order=3,
        weight=0.2,
        depends_on=("colmap", "3dgs"),
        input_hints=("colmap/sparse", "output/.../point_cloud.ply"),
    ),
}

KNOWN_STAGE_IDS = frozenset(STAGE_DEFINITIONS)
KNOWN_OUTPUT_IDS = frozenset(OUTPUT_DEFINITIONS)

PRESETS = {
    "standard": {"label": "Standard quality"},
    "small": {"label": "Small / fast", "gs_preset": "small"},
    "mid": {"label": "Medium quality", "gs_preset": "mid"},
    "high": {"label": "High quality", "gs_preset": "high"},
}
