from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .colmap import ColmapJobConfig
from .gaussian_wrapping import GaussianWrappingJobConfig
from .gs import GsJobConfig
from .langsplat import LangSplatJobConfig

__all__ = [
    "Settings",
    "CorsSettings",
    "ColmapJobConfig",
    "GaussianWrappingJobConfig",
    "GsJobConfig",
    "LangSplatJobConfig",
    "get_settings",
]

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SERVER_CONFIG_PATH = _PACKAGE_ROOT / "configs" / "server" / "active.yaml"


@dataclass(frozen=True)
class CorsSettings:
    allow_origins: tuple[str, ...]
    allow_credentials: bool
    allow_methods: tuple[str, ...]
    allow_headers: tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    data_root: Path
    jobs_root: Path
    ckpts_root: Path
    task_server_container_name: str
    cors: CorsSettings


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML 根节点必须是对象: {path}")
    return payload


def _as_str_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} 必须是非空字符串列表")
    return tuple(str(item) for item in value)


def load_server_settings(path: Path | None = None) -> Settings:
    config_path = path or SERVER_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"服务配置文件不存在: {config_path}")

    payload = _load_yaml(config_path)
    cors_payload = dict(payload.get("cors") or {})

    return Settings(
        data_root=Path(str(payload.get("data_root", "/data"))),
        jobs_root=Path(str(payload.get("jobs_root", "/data/jobs"))),
        ckpts_root=Path(str(payload.get("ckpts_root", "/workspace/ckpts"))),
        task_server_container_name=str(
            payload.get("task_server_container_name", "visionary-task-server")
        ),
        cors=CorsSettings(
            allow_origins=_as_str_list(cors_payload.get("allow_origins"), "cors.allow_origins"),
            allow_credentials=bool(cors_payload.get("allow_credentials", False)),
            allow_methods=_as_str_list(
                cors_payload.get("allow_methods", ["GET", "POST"]),
                "cors.allow_methods",
            ),
            allow_headers=_as_str_list(
                cors_payload.get("allow_headers", ["*"]),
                "cors.allow_headers",
            ),
        ),
    )


@lru_cache
def get_settings() -> Settings:
    return load_server_settings()
