from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from ..settings.colmap import ColmapJobConfig
from ..settings.dgs_to_pc import DgsToPcJobConfig
from ..settings.gaussian_wrapping import GaussianWrappingJobConfig
from ..settings.gs import GsJobConfig
from ..settings.gw_train import GwTrainJobConfig
from ..settings.langsplat import LangSplatJobConfig

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_CONFIGS_ROOT = _PACKAGE_ROOT / "configs"

STAGE_IDS = ("colmap", "3dgs", "gw-train", "langsplat", "gaussian-wrapping", "3dgs-to-pc")

ConfigFactory = Callable[[dict[str, Any]], Any]

CONFIG_FACTORIES: dict[str, ConfigFactory] = {
    "colmap": ColmapJobConfig.from_merged_dict,
    "3dgs": GsJobConfig.from_merged_dict,
    "gw-train": GwTrainJobConfig.from_merged_dict,
    "langsplat": LangSplatJobConfig.from_merged_dict,
    "gaussian-wrapping": GaussianWrappingJobConfig.from_merged_dict,
    "3dgs-to-pc": DgsToPcJobConfig.from_merged_dict,
}


def stage_config_dir(stage_id: str) -> Path:
    return _CONFIGS_ROOT / stage_id


def default_config_path(stage_id: str) -> Path:
    return stage_config_dir(stage_id) / "default.yaml"


@lru_cache
def stage_preset_paths(stage_id: str) -> dict[str, Path]:
    directory = stage_config_dir(stage_id)
    if not directory.is_dir():
        return {}
    return {
        path.stem: path
        for path in sorted(directory.glob("*.yaml"))
        if path.name != "default.yaml"
    }
