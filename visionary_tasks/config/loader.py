from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..jobs.paths import JobPaths
from ..settings import Settings
from ..settings.colmap import ColmapJobConfig
from ..settings.dgs_to_pc import DgsToPcJobConfig
from ..settings.gaussian_wrapping import GaussianWrappingJobConfig
from ..settings.gs import GsJobConfig
from ..settings.langsplat import LangSplatJobConfig
from .registry import CONFIG_FACTORIES, DEFAULT_CONFIG_PATHS, GS_PRESET_PATHS, STAGE_IDS


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


def _write_job_config(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def _resolve_stage_config(
    stage_id: str,
    paths: JobPaths | None = None,
    override: dict[str, Any] | None = None,
    preset: str | None = None,
) -> dict[str, Any]:
    merged = load_yaml(DEFAULT_CONFIG_PATHS[stage_id])
    if stage_id == "3dgs" and preset and preset in GS_PRESET_PATHS:
        merged = deep_merge(merged, load_yaml(GS_PRESET_PATHS[preset]))
    if paths is not None:
        job_config = paths.stage_config_path(stage_id)
        if job_config.exists():
            merged = deep_merge(merged, load_yaml(job_config))
    if override:
        merged = deep_merge(merged, override)
    return merged


def materialize_stage_config(
    stage_id: str,
    paths: JobPaths,
    override: dict[str, Any] | None = None,
    preset: str | None = None,
    gs_output_iteration: int | None = None,
) -> Any:
    merged = _resolve_stage_config(stage_id, paths=None, override=override, preset=preset)
    config = CONFIG_FACTORIES[stage_id](merged)
    if stage_id == "gaussian-wrapping" and gs_output_iteration is not None:
        config.sync_gs_iteration(gs_output_iteration)
    if stage_id == "3dgs-to-pc" and gs_output_iteration is not None:
        config.sync_iteration(gs_output_iteration)
    _write_job_config(paths.stage_config_path(stage_id), config.to_dict())
    return config


def load_stage_config(stage_id: str, settings: Settings, paths: JobPaths) -> Any:
    config_path = paths.stage_config_path(stage_id)
    if not config_path.exists():
        return materialize_stage_config(stage_id, paths)
    merged = load_yaml(config_path)
    config = CONFIG_FACTORIES[stage_id](merged)
    if stage_id == "gaussian-wrapping":
        gs_config = load_stage_config("3dgs", settings, paths)
        config.sync_gs_iteration(gs_config.output_iteration)
    if stage_id == "3dgs-to-pc":
        gs_config = load_stage_config("3dgs", settings, paths)
        config.sync_iteration(gs_config.output_iteration)
    return config


def materialize_job_configs(
    settings: Settings,
    paths: JobPaths,
    stage_ids: list[str],
    overrides: dict[str, dict[str, Any] | None] | None = None,
    preset: str | None = None,
) -> GsJobConfig:
    overrides = overrides or {}
    gs_preset = preset if preset in GS_PRESET_PATHS else None
    gs_config = materialize_stage_config(
        "3dgs",
        paths,
        override=overrides.get("3dgs"),
        preset=gs_preset,
    )
    for stage_id in STAGE_IDS:
        if stage_id == "3dgs" or stage_id not in stage_ids:
            continue
        if stage_id in ("gaussian-wrapping", "3dgs-to-pc"):
            materialize_stage_config(
                stage_id,
                paths,
                override=overrides.get(stage_id),
                gs_output_iteration=gs_config.output_iteration,
            )
        else:
            materialize_stage_config(stage_id, paths, override=overrides.get(stage_id))
    return gs_config


def load_gs_job_config(settings: Settings, paths: JobPaths) -> GsJobConfig:
    return load_stage_config("3dgs", settings, paths)


def load_colmap_job_config(settings: Settings, paths: JobPaths) -> ColmapJobConfig:
    return load_stage_config("colmap", settings, paths)


def load_langsplat_job_config(settings: Settings, paths: JobPaths) -> LangSplatJobConfig:
    return load_stage_config("langsplat", settings, paths)


def load_gaussian_wrapping_job_config(
    settings: Settings,
    paths: JobPaths,
) -> GaussianWrappingJobConfig:
    return load_stage_config("gaussian-wrapping", settings, paths)


def load_3dgs_to_pc_job_config(settings: Settings, paths: JobPaths) -> DgsToPcJobConfig:
    return load_stage_config("3dgs-to-pc", settings, paths)
