from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputDefinition:
    id: str
    label: str
    required_stages: tuple[str, ...]
    ply_mode_stages: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageDefinition:
    id: str
    label: str
    order: int
    weight: float
    depends_on: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    input_hints: tuple[str, ...]


@dataclass(frozen=True)
class InputModeDefinition:
    id: str
    label: str
    file_types: tuple[str, ...]
    allowed_outputs: tuple[str, ...]


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
        label="Mesh",
        required_stages=("colmap", "3dgs", "gaussian-wrapping"),
        ply_mode_stages=("3dgs-to-pc",),
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
        required_artifacts=("input_images",),
        input_hints=("input/ 下有图像",),
    ),
    "3dgs": StageDefinition(
        id="3dgs",
        label="3DGS",
        order=1,
        weight=0.6,
        depends_on=("colmap",),
        required_artifacts=("colmap_sparse",),
        input_hints=("colmap/sparse",),
    ),
    "langsplat": StageDefinition(
        id="langsplat",
        label="LangSplatV2",
        order=2,
        weight=0.15,
        depends_on=("colmap", "3dgs"),
        required_artifacts=("colmap_sparse", "gs_checkpoint"),
        input_hints=("colmap/sparse", "output/chkpnt{N}.pth"),
    ),
    "gaussian-wrapping": StageDefinition(
        id="gaussian-wrapping",
        label="Mesh",
        order=3,
        weight=0.2,
        depends_on=("colmap", "3dgs"),
        required_artifacts=("colmap_sparse", "point_cloud_ply"),
        input_hints=("colmap/sparse", "output/.../point_cloud.ply"),
    ),
    "3dgs-to-pc": StageDefinition(
        id="3dgs-to-pc",
        label="PLY Mesh",
        order=3,
        weight=0.2,
        depends_on=(),
        required_artifacts=("point_cloud_ply",),
        input_hints=("output/.../point_cloud.ply",),
    ),
}

PLY_MODE_STAGE_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "3dgs-to-pc": ("point_cloud_ply",),
}

INPUT_MODE_DEFINITIONS: dict[str, InputModeDefinition] = {
    "images": InputModeDefinition(
        id="images",
        label="Images",
        file_types=(".jpg", ".jpeg", ".png", ".bmp", ".webp"),
        allowed_outputs=("point_cloud", "mesh", "language_model"),
    ),
    "native_3dgs_ply": InputModeDefinition(
        id="native_3dgs_ply",
        label="Native 3DGS Point Cloud PLY",
        file_types=(".ply",),
        allowed_outputs=("mesh",),
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
