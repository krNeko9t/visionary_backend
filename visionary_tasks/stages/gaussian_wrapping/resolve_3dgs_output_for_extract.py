from __future__ import annotations

from dataclasses import dataclass

from ...jobs.paths import JobPaths
from ...settings.gs import GsJobConfig

CONTAINER_COLMAP_PATH = "/job/colmap"


@dataclass(frozen=True)
class ExtractInputs:
    colmap_path: str
    model_path: str
    iteration: int


def resolve(paths: JobPaths, gs: GsJobConfig) -> ExtractInputs:
    return ExtractInputs(
        colmap_path=CONTAINER_COLMAP_PATH,
        model_path=f"/job/{gs.output_relative}",
        iteration=gs.output_iteration,
    )
