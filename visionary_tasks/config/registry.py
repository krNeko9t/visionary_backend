from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..settings.colmap import ColmapJobConfig
from ..settings.gaussian_wrapping import GaussianWrappingJobConfig
from ..settings.gs import GsJobConfig
from ..settings.langsplat import LangSplatJobConfig

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent

STAGE_IDS = ("colmap", "3dgs", "langsplat", "gaussian-wrapping")

DEFAULT_CONFIG_PATHS: dict[str, Path] = {
    "colmap": _PACKAGE_ROOT / "configs" / "colmap" / "default.yaml",
    "3dgs": _PACKAGE_ROOT / "configs" / "3dgs" / "default.yaml",
    "langsplat": _PACKAGE_ROOT / "configs" / "langsplat" / "default.yaml",
    "gaussian-wrapping": _PACKAGE_ROOT / "configs" / "gaussian-wrapping" / "default.yaml",
}

GS_PRESET_PATHS: dict[str, Path] = {
    "small": _PACKAGE_ROOT / "configs" / "3dgs" / "small.yaml",
    "mid": _PACKAGE_ROOT / "configs" / "3dgs" / "mid.yaml",
    "high": _PACKAGE_ROOT / "configs" / "3dgs" / "high.yaml",
}

ConfigFactory = Callable[[dict[str, Any]], Any]

CONFIG_FACTORIES: dict[str, ConfigFactory] = {
    "colmap": ColmapJobConfig.from_merged_dict,
    "3dgs": GsJobConfig.from_merged_dict,
    "langsplat": LangSplatJobConfig.from_merged_dict,
    "gaussian-wrapping": GaussianWrappingJobConfig.from_merged_dict,
}
