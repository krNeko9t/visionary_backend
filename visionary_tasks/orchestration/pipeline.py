from collections.abc import Callable
from dataclasses import dataclass

from ..executors import colmap, gaussian_wrapping, gs, langsplat
from ..jobs.paths import JobPaths
from ..settings import Settings
from .inputs import (
    missing_3dgs_inputs,
    missing_colmap_inputs,
    missing_gaussian_wrapping_inputs,
    missing_langsplat_inputs,
)

InputChecker = Callable[[JobPaths, Settings], list[str]]
ExecutorFn = Callable[[Settings, JobPaths], dict[str, str]]


@dataclass(frozen=True)
class StageSpec:
    id: str
    label: str
    order: int
    check_inputs: InputChecker
    input_hints: tuple[str, ...]
    run: ExecutorFn
    download_keys: tuple[str, ...]


PIPELINE: tuple[StageSpec, ...] = (
    StageSpec(
        id="colmap",
        label="COLMAP",
        order=0,
        check_inputs=missing_colmap_inputs,
        input_hints=("input/ 下有图像",),
        run=colmap.run,
        download_keys=(),
    ),
    StageSpec(
        id="3dgs",
        label="3DGS",
        order=1,
        check_inputs=missing_3dgs_inputs,
        input_hints=("colmap/sparse",),
        run=gs.run,
        download_keys=("ply",),
    ),
    StageSpec(
        id="langsplat",
        label="LangSplatV2",
        order=2,
        check_inputs=missing_langsplat_inputs,
        input_hints=("colmap/sparse", "output/chkpnt{N}.pth"),
        run=langsplat.run,
        download_keys=(),
    ),
    StageSpec(
        id="gaussian-wrapping",
        label="Mesh",
        order=3,
        check_inputs=missing_gaussian_wrapping_inputs,
        input_hints=("colmap/sparse", "output/.../point_cloud.ply"),
        run=gaussian_wrapping.run,
        download_keys=("mesh_textured_ply", "mesh_ply"),
    ),
)

STAGE_BY_ID: dict[str, StageSpec] = {spec.id: spec for spec in PIPELINE}
KNOWN_STAGE_IDS: frozenset[str] = frozenset(STAGE_BY_ID)


def get_stage(stage_id: str) -> StageSpec:
    try:
        return STAGE_BY_ID[stage_id]
    except KeyError as exc:
        raise ValueError(f"未知阶段: {stage_id}") from exc


def resolve_enabled(enabled: dict[str, bool]) -> list[str]:
    selected = [spec.id for spec in PIPELINE if enabled.get(spec.id)]
    return selected


def validate_enabled(enabled: dict[str, bool]) -> list[str]:
    if not enabled:
        raise ValueError("enabled 不能为空")
    unknown = [stage_id for stage_id in enabled if stage_id not in KNOWN_STAGE_IDS]
    if unknown:
        raise ValueError(f"未知阶段: {', '.join(unknown)}")
    resolved = resolve_enabled(enabled)
    if not resolved:
        raise ValueError("至少启用一个阶段")
    return resolved


def check_stage_inputs(spec: StageSpec, paths: JobPaths, settings: Settings) -> list[str]:
    return spec.check_inputs(paths, settings)


def download_keys(stage_id: str) -> tuple[str, ...]:
    return get_stage(stage_id).download_keys


def pipeline_public_stages() -> list[dict[str, object]]:
    return [
        {
            "id": spec.id,
            "label": spec.label,
            "order": spec.order,
            "inputs": list(spec.input_hints),
        }
        for spec in PIPELINE
    ]
