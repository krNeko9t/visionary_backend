from __future__ import annotations

from dataclasses import dataclass

from ...jobs.paths import JobPaths
from ...settings import Settings
from ..training_output import TrainOutputConfig, load_mesh_training_config

CONTAINER_COLMAP_PATH = "/job/colmap"


@dataclass(frozen=True)
class ExtractInputs:
    colmap_path: str
    model_path: str
    iteration: int


def resolve(paths: JobPaths, training: TrainOutputConfig) -> ExtractInputs:
    return ExtractInputs(
        colmap_path=CONTAINER_COLMAP_PATH,
        model_path=f"/job/{training.output_relative}",
        iteration=training.output_iteration,
    )


def resolve_for_job(settings: Settings, paths: JobPaths) -> ExtractInputs:
    return resolve(paths, load_mesh_training_config(settings, paths))
