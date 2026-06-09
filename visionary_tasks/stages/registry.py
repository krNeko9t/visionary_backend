from __future__ import annotations

from collections.abc import Callable

from ..jobs.paths import JobPaths
from ..settings import Settings
from ..workers.contract import WorkerResult
from . import colmap, dgs_to_pc, gs, langsplat
from .gaussian_wrapping import run as gaussian_wrapping_run
from .inputs import (
    missing_3dgs_inputs,
    missing_3dgs_to_pc_inputs,
    missing_colmap_inputs,
    missing_gaussian_wrapping_inputs,
    missing_langsplat_inputs,
)

StageRunner = Callable[[Settings, JobPaths], WorkerResult]
InputChecker = Callable[[JobPaths, Settings], list[str]]

STAGE_RUNNERS: dict[str, StageRunner] = {
    "colmap": colmap.run,
    "3dgs": gs.run,
    "langsplat": langsplat.run,
    "gaussian-wrapping": gaussian_wrapping_run.run,
    "3dgs-to-pc": dgs_to_pc.run,
}

INPUT_CHECKERS: dict[str, InputChecker] = {
    "colmap": missing_colmap_inputs,
    "3dgs": missing_3dgs_inputs,
    "langsplat": missing_langsplat_inputs,
    "gaussian-wrapping": missing_gaussian_wrapping_inputs,
    "3dgs-to-pc": missing_3dgs_to_pc_inputs,
}


def get_stage_runner(stage_id: str) -> StageRunner:
    try:
        return STAGE_RUNNERS[stage_id]
    except KeyError as exc:
        raise ValueError(f"未知阶段: {stage_id}") from exc


def check_stage_inputs(stage_id: str, paths: JobPaths, settings: Settings) -> list[str]:
    try:
        checker = INPUT_CHECKERS[stage_id]
    except KeyError as exc:
        raise ValueError(f"未知阶段: {stage_id}") from exc
    return checker(paths, settings)
