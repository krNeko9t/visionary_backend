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
from ..settings.gw_train import GwTrainJobConfig
from ..settings.langsplat import LangSplatJobConfig
from .registry import CONFIG_FACTORIES, STAGE_IDS, default_config_path, stage_preset_paths


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


def validate_stage_presets(stage_presets: dict[str, str]) -> None:
    for stage_id, preset_name in stage_presets.items():
        if stage_id not in STAGE_IDS:
            raise ValueError(f"未知 stage: {stage_id}")
        if preset_name not in stage_preset_paths(stage_id):
            raise ValueError(f"未知 preset: {preset_name} (stage={stage_id})")


def stage_presets_from_options(options: dict[str, Any]) -> dict[str, str]:
    raw = options.get("stage_presets")
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


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
    merged = load_yaml(default_config_path(stage_id))
    preset_paths = stage_preset_paths(stage_id)
    if preset and preset in preset_paths:
        merged = deep_merge(merged, load_yaml(preset_paths[preset]))
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
    if stage_id == "3dgs-to-pc":
        gs_config = load_stage_config("3dgs", settings, paths)
        config.sync_iteration(gs_config.output_iteration)
    return config


def materialize_job_configs(
    settings: Settings,
    paths: JobPaths,
    stage_ids: list[str],
    overrides: dict[str, dict[str, Any] | None] | None = None,
    stage_presets: dict[str, str] | None = None,
) -> GsJobConfig | GwTrainJobConfig:
    del settings
    overrides = overrides or {}
    stage_presets = stage_presets or {}
    output_config: GsJobConfig | GwTrainJobConfig | None = None

    if "3dgs" in stage_ids:
        output_config = materialize_stage_config(
            "3dgs",
            paths,
            override=overrides.get("3dgs"),
            preset=stage_presets.get("3dgs"),
        )
    elif "gw-train" in stage_ids:
        output_config = materialize_stage_config(
            "gw-train",
            paths,
            override=overrides.get("gw-train"),
            preset=stage_presets.get("gw-train"),
        )

    for stage_id in STAGE_IDS:
        if stage_id in {"3dgs", "gw-train"} or stage_id not in stage_ids:
            continue
        if stage_id == "3dgs-to-pc":
            if output_config is None:
                raise ValueError("3dgs-to-pc 需要 3dgs 或 gw-train 阶段")
            materialize_stage_config(
                stage_id,
                paths,
                override=overrides.get(stage_id),
                gs_output_iteration=output_config.output_iteration,
            )
        else:
            materialize_stage_config(
                stage_id,
                paths,
                override=overrides.get(stage_id),
                preset=stage_presets.get(stage_id),
            )

    if output_config is None:
        raise ValueError("任务计划必须包含 3dgs 或 gw-train 阶段")
    return output_config


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


def load_gw_train_job_config(settings: Settings, paths: JobPaths) -> GwTrainJobConfig:
    return load_stage_config("gw-train", settings, paths)


def load_3dgs_to_pc_job_config(settings: Settings, paths: JobPaths) -> DgsToPcJobConfig:
    return load_stage_config("3dgs-to-pc", settings, paths)
