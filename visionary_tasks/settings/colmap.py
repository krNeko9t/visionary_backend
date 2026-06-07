from __future__ import annotations

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
    worker_image: str
    converter: ColmapConverterConfig

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "ColmapJobConfig":
        return cls(
            worker_image=str(payload.get("worker_image", "visionary-colmap-worker:local")),
            converter=ColmapConverterConfig(**dict(payload.get("converter") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_image": self.worker_image,
            "converter": asdict(self.converter),
        }

    def to_convert_command(self, source_path: str) -> list[str]:
        command = ["--source_path", source_path]
        for key, value in asdict(self.converter).items():
            command.extend(format_cli_arg(key, value))
        return command
