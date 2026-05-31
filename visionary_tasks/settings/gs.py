from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

MODEL_SHORTHAND = {
    "resolution": "-r",
    "white_background": "-w",
    "images": "-i",
    "depths": "-d",
}

MODEL_SKIP = {"source_path", "model_path"}
TRAINING_SKIP = {"output_iteration"}


def _ensure_iteration_present(values: list[int], iteration: int, field_name: str) -> list[int]:
    normalized = sorted({int(value) for value in values})
    if iteration not in normalized:
        raise ValueError(
            f"training.{field_name} 必须包含 output_iteration={iteration}"
        )
    return normalized


@dataclass
class GsModelConfig:
    sh_degree: int = 3
    images: str = "images"
    depths: str = ""
    resolution: int = -1
    white_background: bool = False
    train_test_exp: bool = False
    data_device: str = "cuda"
    eval: bool = False


@dataclass
class GsOptimizationConfig:
    iterations: int = 30_000
    position_lr_init: float = 0.00016
    position_lr_final: float = 0.0000016
    position_lr_delay_mult: float = 0.01
    position_lr_max_steps: int = 30_000
    feature_lr: float = 0.0025
    opacity_lr: float = 0.025
    scaling_lr: float = 0.005
    rotation_lr: float = 0.001
    exposure_lr_init: float = 0.01
    exposure_lr_final: float = 0.001
    exposure_lr_delay_steps: int = 0
    exposure_lr_delay_mult: float = 0.0
    percent_dense: float = 0.01
    lambda_dssim: float = 0.2
    densification_interval: int = 100
    opacity_reset_interval: int = 3000
    densify_from_iter: int = 500
    densify_until_iter: int = 15_000
    densify_grad_threshold: float = 0.0002
    depth_l1_weight_init: float = 1.0
    depth_l1_weight_final: float = 0.01
    random_background: bool = False
    optimizer_type: str = "default"


@dataclass
class GsPipelineConfig:
    convert_SHs_python: bool = False
    compute_cov3D_python: bool = False
    debug: bool = False
    antialiasing: bool = False


@dataclass
class GsTrainingConfig:
    output_iteration: int = 500
    save_iterations: list[int] = field(default_factory=lambda: [500])
    checkpoint_iterations: list[int] = field(default_factory=lambda: [500])
    test_iterations: list[int] = field(default_factory=lambda: [7000, 30_000])
    disable_viewer: bool = True
    quiet: bool = True
    ip: str = "127.0.0.1"
    port: int = 6009
    debug_from: int = -1
    detect_anomaly: bool = False
    start_checkpoint: str | None = None


@dataclass
class GsJobConfig:
    model: GsModelConfig
    optimization: GsOptimizationConfig
    pipeline: GsPipelineConfig
    training: GsTrainingConfig

    @property
    def output_iteration(self) -> int:
        return self.training.output_iteration

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "GsJobConfig":
        config = cls(
            model=GsModelConfig(**dict(payload.get("model") or {})),
            optimization=GsOptimizationConfig(**dict(payload.get("optimization") or {})),
            pipeline=GsPipelineConfig(**dict(payload.get("pipeline") or {})),
            training=GsTrainingConfig(**dict(payload.get("training") or {})),
        )
        return config.validate()

    def validate(self) -> "GsJobConfig":
        output_iteration = self.training.output_iteration
        self.training.save_iterations = _ensure_iteration_present(
            self.training.save_iterations,
            output_iteration,
            "save_iterations",
        )
        self.training.checkpoint_iterations = _ensure_iteration_present(
            self.training.checkpoint_iterations,
            output_iteration,
            "checkpoint_iterations",
        )
        return self

    def apply_env_overrides(self) -> "GsJobConfig":
        iterations_env = os.getenv("GS_ITERATIONS")
        if iterations_env is not None:
            self.optimization.iterations = int(iterations_env)

        save_iteration_env = os.getenv("GS_SAVE_ITERATION")
        if save_iteration_env is not None:
            output_iteration = int(save_iteration_env)
            self.training.output_iteration = output_iteration
            self.training.save_iterations = _ensure_iteration_present(
                self.training.save_iterations,
                output_iteration,
                "save_iterations",
            )
            self.training.checkpoint_iterations = _ensure_iteration_present(
                self.training.checkpoint_iterations,
                output_iteration,
                "checkpoint_iterations",
            )

        return self.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": asdict(self.model),
            "optimization": asdict(self.optimization),
            "pipeline": asdict(self.pipeline),
            "training": asdict(self.training),
        }

    def to_train_command(self, source_dir: str, model_path: str) -> list[str]:
        command = ["python", "train.py", "-s", source_dir, "-m", model_path]

        for key, value in asdict(self.model).items():
            if key in MODEL_SKIP:
                continue
            command.extend(_format_cli_arg(key, value, shorthand=MODEL_SHORTHAND.get(key)))

        for key, value in asdict(self.optimization).items():
            command.extend(_format_cli_arg(key, value))

        for key, value in asdict(self.pipeline).items():
            command.extend(_format_cli_arg(key, value))

        for key, value in asdict(self.training).items():
            if key in TRAINING_SKIP:
                continue
            command.extend(_format_cli_arg(key, value))

        return command


def _format_cli_arg(
    key: str,
    value: Any,
    shorthand: str | None = None,
) -> list[str]:
    flag = shorthand or f"--{key}"

    if value is None:
        return []

    if isinstance(value, bool):
        return [flag] if value else []

    if isinstance(value, list):
        if not value:
            return []
        return [flag, *[str(item) for item in value]]

    if isinstance(value, str) and not value:
        return []

    return [flag, str(value)]
