from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..jobs.paths import JobPaths
from ..settings import Settings
from ..settings.colmap import ColmapJobConfig
from ..settings.gaussian_wrapping import GaussianWrappingJobConfig
from ..settings.gs import GsJobConfig
from ..settings.langsplat import LangSplatJobConfig

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIGS = {
    "3dgs": _PACKAGE_ROOT / "configs" / "3dgs" / "default.yaml",
    "colmap": _PACKAGE_ROOT / "configs" / "colmap" / "default.yaml",
    "langsplat": _PACKAGE_ROOT / "configs" / "langsplat" / "default.yaml",
    "gaussian-wrapping": _PACKAGE_ROOT / "configs" / "gaussian-wrapping" / "default.yaml",
}


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


def resolve_gs_config(
    settings: Settings | None = None,
    paths: JobPaths | None = None,
    override: dict[str, Any] | None = None,
) -> GsJobConfig:
    del settings
    merged = load_yaml(DEFAULT_CONFIGS["3dgs"])
    if paths is not None:
        job_config = paths.gs_config_path()
        if job_config.exists():
            merged = deep_merge(merged, load_yaml(job_config))
    if override:
        merged = deep_merge(merged, override)
    return GsJobConfig.from_merged_dict(merged)


def materialize_gs_config(
    settings: Settings,
    paths: JobPaths,
    override: dict[str, Any] | None = None,
) -> GsJobConfig:
    config = resolve_gs_config(settings, override=override)
    _write_job_config(paths.gs_config_path(), config.to_dict())
    return config


def load_gs_job_config(settings: Settings, paths: JobPaths) -> GsJobConfig:
    del settings
    config_path = paths.gs_config_path()
    if not config_path.exists():
        return materialize_gs_config(settings, paths)
    merged = load_yaml(config_path)
    return GsJobConfig.from_merged_dict(merged)


def resolve_colmap_config(
    override: dict[str, Any] | None = None,
) -> ColmapJobConfig:
    merged = load_yaml(DEFAULT_CONFIGS["colmap"])
    if override:
        merged = deep_merge(merged, override)
    return ColmapJobConfig.from_merged_dict(merged)


def materialize_colmap_config(
    paths: JobPaths,
    override: dict[str, Any] | None = None,
) -> ColmapJobConfig:
    config = resolve_colmap_config(override=override)
    _write_job_config(paths.colmap_config_path(), config.to_dict())
    return config


def load_colmap_job_config(settings: Settings, paths: JobPaths) -> ColmapJobConfig:
    del settings
    config_path = paths.colmap_config_path()
    if not config_path.exists():
        return materialize_colmap_config(paths)
    merged = load_yaml(config_path)
    return ColmapJobConfig.from_merged_dict(merged)


def resolve_langsplat_config(
    override: dict[str, Any] | None = None,
) -> LangSplatJobConfig:
    merged = load_yaml(DEFAULT_CONFIGS["langsplat"])
    if override:
        merged = deep_merge(merged, override)
    return LangSplatJobConfig.from_merged_dict(merged)


def materialize_langsplat_config(
    paths: JobPaths,
    override: dict[str, Any] | None = None,
) -> LangSplatJobConfig:
    config = resolve_langsplat_config(override=override)
    _write_job_config(paths.langsplat_config_path(), config.to_dict())
    return config


def load_langsplat_job_config(settings: Settings, paths: JobPaths) -> LangSplatJobConfig:
    del settings
    config_path = paths.langsplat_config_path()
    if not config_path.exists():
        return materialize_langsplat_config(paths)
    merged = load_yaml(config_path)
    return LangSplatJobConfig.from_merged_dict(merged)


def resolve_gaussian_wrapping_config(
    override: dict[str, Any] | None = None,
    gs_output_iteration: int | None = None,
) -> GaussianWrappingJobConfig:
    merged = load_yaml(DEFAULT_CONFIGS["gaussian-wrapping"])
    if override:
        merged = deep_merge(merged, override)
    config = GaussianWrappingJobConfig.from_merged_dict(merged)
    if gs_output_iteration is not None:
        config.sync_gs_iteration(gs_output_iteration)
    return config


def materialize_gaussian_wrapping_config(
    settings: Settings,
    paths: JobPaths,
    override: dict[str, Any] | None = None,
    gs_output_iteration: int | None = None,
) -> GaussianWrappingJobConfig:
    if gs_output_iteration is None:
        gs_output_iteration = resolve_gs_config(settings, override=None).output_iteration
    config = resolve_gaussian_wrapping_config(
        override=override,
        gs_output_iteration=gs_output_iteration,
    )
    _write_job_config(paths.gaussian_wrapping_config_path(), config.to_dict())
    return config


def load_gaussian_wrapping_job_config(
    settings: Settings,
    paths: JobPaths,
) -> GaussianWrappingJobConfig:
    gs_output_iteration = load_gs_job_config(settings, paths).output_iteration
    config_path = paths.gaussian_wrapping_config_path()
    if not config_path.exists():
        return materialize_gaussian_wrapping_config(
            settings,
            paths,
            gs_output_iteration=gs_output_iteration,
        )
    merged = load_yaml(config_path)
    config = GaussianWrappingJobConfig.from_merged_dict(merged)
    config.sync_gs_iteration(gs_output_iteration)
    return config


def materialize_job_configs(
    settings: Settings,
    paths: JobPaths,
    overrides: dict[str, dict[str, Any] | None] | None = None,
) -> GsJobConfig:
    overrides = overrides or {}
    gs_config = materialize_gs_config(settings, paths, override=overrides.get("3dgs"))
    materialize_colmap_config(paths, override=overrides.get("colmap"))
    materialize_langsplat_config(paths, override=overrides.get("langsplat"))
    materialize_gaussian_wrapping_config(
        settings,
        paths,
        override=overrides.get("gaussian-wrapping"),
        gs_output_iteration=gs_config.output_iteration,
    )
    return gs_config
