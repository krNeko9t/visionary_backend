from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..jobs.paths import JobPaths
from ..settings import Settings
from ..settings.gs import GsJobConfig

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GS_CONFIG = _PACKAGE_ROOT / "configs" / "3dgs" / "default.yaml"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML 根节点必须是对象: {path}")
    return payload


def resolve_gs_config(
    settings: Settings | None = None,
    paths: JobPaths | None = None,
    override: dict[str, Any] | None = None,
) -> GsJobConfig:
    del settings
    merged = load_yaml(DEFAULT_GS_CONFIG)
    if paths is not None:
        job_config = paths.gs_config_path()
        if job_config.exists():
            merged = deep_merge(merged, load_yaml(job_config))
    if override:
        merged = deep_merge(merged, override)
    return GsJobConfig.from_merged_dict(merged).apply_env_overrides()


def materialize_gs_config(
    settings: Settings,
    paths: JobPaths,
    override: dict[str, Any] | None = None,
) -> GsJobConfig:
    config = resolve_gs_config(settings, override=override)
    config_path = paths.gs_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False, allow_unicode=True)
    return config


def load_gs_job_config(settings: Settings, paths: JobPaths) -> GsJobConfig:
    del settings
    config_path = paths.gs_config_path()
    if not config_path.exists():
        return materialize_gs_config(settings, paths)
    merged = load_yaml(config_path)
    return GsJobConfig.from_merged_dict(merged).apply_env_overrides()
