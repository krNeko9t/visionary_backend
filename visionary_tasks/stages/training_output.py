from __future__ import annotations

from typing import Protocol

from ..config.loader import load_gs_job_config, load_gw_train_job_config
from ..jobs.paths import JobPaths
from ..jobs.storage import read_job_state
from ..settings import Settings
from ..settings.gs import GsJobConfig
from ..settings.gw_train import GwTrainJobConfig


class TrainOutputConfig(Protocol):
    output_relative: str
    output_iteration: int


def load_mesh_training_config(
    settings: Settings,
    paths: JobPaths,
) -> GsJobConfig | GwTrainJobConfig:
    state = read_job_state(paths.job_state_file)
    if state is not None and "gw-train" in state.planned_stages:
        return load_gw_train_job_config(settings, paths)
    return load_gs_job_config(settings, paths)
