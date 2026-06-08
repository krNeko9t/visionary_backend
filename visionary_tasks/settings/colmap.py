from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .cli import format_cli_arg


@dataclass
class ColmapSiftConfig:
    max_image_size: int | None = None
    max_num_features: int | None = None


@dataclass
class ColmapMapperConfig:
    multiple_models: int | None = None
    ba_global_function_tolerance: float | None = None


@dataclass
class ColmapConverterConfig:
    camera: str = "OPENCV"
    matcher: str = "exhaustive"
    no_gpu: bool = False
    skip_matching: bool = False
    resize: bool = False
    colmap_executable: str = ""
    magick_executable: str = ""
    sift: ColmapSiftConfig = field(default_factory=ColmapSiftConfig)
    mapper: ColmapMapperConfig = field(default_factory=ColmapMapperConfig)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ColmapConverterConfig":
        data = dict(payload)
        sift = ColmapSiftConfig(**dict(data.pop("sift", {}) or {}))
        mapper = ColmapMapperConfig(**dict(data.pop("mapper", {}) or {}))
        return cls(sift=sift, mapper=mapper, **data)


@dataclass
class ColmapJobConfig:
    worker_image: str
    converter: ColmapConverterConfig

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "ColmapJobConfig":
        return cls(
            worker_image=str(payload.get("worker_image", "visionary-colmap-worker:local")),
            converter=ColmapConverterConfig.from_dict(dict(payload.get("converter") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_image": self.worker_image,
            "converter": asdict(self.converter),
        }

    def to_convert_command(self, source_path: str) -> list[str]:
        command = ["--source_path", source_path]
        converter = self.converter
        command.extend(format_cli_arg("camera", converter.camera))
        command.extend(format_cli_arg("matcher", converter.matcher))
        command.extend(format_cli_arg("no_gpu", converter.no_gpu))
        command.extend(format_cli_arg("skip_matching", converter.skip_matching))
        command.extend(format_cli_arg("resize", converter.resize))
        command.extend(format_cli_arg("colmap_executable", converter.colmap_executable))
        command.extend(format_cli_arg("magick_executable", converter.magick_executable))

        sift = converter.sift
        if sift.max_image_size is not None:
            command.extend(format_cli_arg("sift_max_image_size", sift.max_image_size))
        if sift.max_num_features is not None:
            command.extend(format_cli_arg("sift_max_num_features", sift.max_num_features))

        mapper = converter.mapper
        if mapper.multiple_models is not None:
            command.extend(format_cli_arg("mapper_multiple_models", mapper.multiple_models))
        if mapper.ba_global_function_tolerance is not None:
            command.extend(
                format_cli_arg(
                    "mapper_ba_global_function_tolerance",
                    mapper.ba_global_function_tolerance,
                )
            )
        return command
