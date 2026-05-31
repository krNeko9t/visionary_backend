from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from .cli import format_cli_arg


@dataclass
class ColmapConverterConfig:
    camera: str = "OPENCV"
    no_gpu: bool = False
    skip_matching: bool = False
    resize: bool = False
    colmap_executable: str = ""
    magick_executable: str = ""


@dataclass
class ColmapJobConfig:
    converter: ColmapConverterConfig

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "ColmapJobConfig":
        return cls(converter=ColmapConverterConfig(**dict(payload.get("converter") or {})))

    def apply_env_overrides(self) -> "ColmapJobConfig":
        camera_env = os.getenv("COLMAP_CAMERA_MODEL")
        if camera_env is not None:
            self.converter.camera = camera_env
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"converter": asdict(self.converter)}

    def to_convert_command(self, source_path: str) -> list[str]:
        command = ["--source_path", source_path]
        for key, value in asdict(self.converter).items():
            command.extend(format_cli_arg(key, value))
        return command
