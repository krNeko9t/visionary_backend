from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .cli import format_cli_arg, format_negatable_bool

TRAIN_SCRIPT = "gaussian_wrapping/train.py"

MODEL_SHORTHAND = {
    "resolution": "-r",
    "white_background": "-w",
    "images": "-i",
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
class GwTrainRuntimeConfig:
    output_relative: str = "output"


@dataclass
class GwTrainModelConfig:
    sh_degree: int = 3
    images: str = "images"
    resolution: int = -1
    white_background: bool = False
    data_device: str = "cpu"
    eval: bool = False


@dataclass
class GwTrainOptimizationConfig:
    iterations: int = 30_000
    position_lr_init: float = 0.00016
    position_lr_final: float = 0.0000016
    position_lr_delay_mult: float = 0.01
    position_lr_max_steps: int = 30_000
    feature_dc_lr: float = 0.0013
    feature_rest_lr: float = 0.00011
    opacity_lr: float = 0.05
    scaling_lr: float = 0.005
    rotation_lr: float = 0.001
    percent_dense: float = 0.01
    lambda_dssim: float = 0.2
    densification_interval: int = 100
    opacity_reset_interval: int = 3000
    densify_from_iter: int = 500
    densify_until_iter: int = 15_000
    densify_grad_threshold: float = 0.0002
    random_background: bool = False


@dataclass
class GwTrainPipelineConfig:
    convert_SHs_python: bool = False
    compute_cov3D_python: bool = False
    debug: bool = False


@dataclass
class GwTrainTrainingConfig:
    output_iteration: int = 30_000
    save_iterations: list[int] = field(default_factory=lambda: [30_000])
    checkpoint_iterations: list[int] = field(default_factory=lambda: [30_000])
    test_iterations: list[int] = field(default_factory=lambda: [7000, 30_000])
    quiet: bool = True
    ip: str = "127.0.0.1"
    port: int = -1
    debug_from: int = -1
    detect_anomaly: bool = False
    start_checkpoint: str | None = None


@dataclass
class GwTrainGwConfig:
    rasterizer: str = "ours"
    exposure_compensation: bool = True
    multiview: bool = True
    multiview_config: str = "fast"
    multiview_factor: float = 1.0
    regularization_from_iter: int = 7_000
    lambda_depth_normal: float = 0.05
    use_max_size_threshold: bool = False
    N_max_gaussians: int | None = 6_000_000
    normal_field_config: str = "default_regular_densification"


@dataclass
class GwTrainJobConfig:
    worker_image: str
    runtime: GwTrainRuntimeConfig
    model: GwTrainModelConfig
    optimization: GwTrainOptimizationConfig
    pipeline: GwTrainPipelineConfig
    training: GwTrainTrainingConfig
    gw: GwTrainGwConfig

    @property
    def output_iteration(self) -> int:
        return self.training.output_iteration

    @property
    def output_relative(self) -> str:
        return self.runtime.output_relative

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> GwTrainJobConfig:
        config = cls(
            worker_image=str(payload.get("worker_image", "gaussian-wrapping:latest")),
            runtime=GwTrainRuntimeConfig(**dict(payload.get("runtime") or {})),
            model=GwTrainModelConfig(**dict(payload.get("model") or {})),
            optimization=GwTrainOptimizationConfig(**dict(payload.get("optimization") or {})),
            pipeline=GwTrainPipelineConfig(**dict(payload.get("pipeline") or {})),
            training=GwTrainTrainingConfig(**dict(payload.get("training") or {})),
            gw=GwTrainGwConfig(**dict(payload.get("gw") or {})),
        )
        return config.validate()

    def validate(self) -> GwTrainJobConfig:
        output_iteration = self.training.output_iteration
        if self.optimization.iterations != output_iteration:
            raise ValueError(
                "optimization.iterations 必须与 training.output_iteration 一致"
            )
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_image": self.worker_image,
            "runtime": asdict(self.runtime),
            "model": asdict(self.model),
            "optimization": asdict(self.optimization),
            "pipeline": asdict(self.pipeline),
            "training": asdict(self.training),
            "gw": asdict(self.gw),
        }

    def to_train_command(self, source_dir: str, model_path: str) -> list[str]:
        command = ["python", TRAIN_SCRIPT, "-s", source_dir, "-m", model_path]

        for key, value in asdict(self.model).items():
            if key in MODEL_SKIP:
                continue
            command.extend(format_cli_arg(key, value, shorthand=MODEL_SHORTHAND.get(key)))

        for key, value in asdict(self.optimization).items():
            command.extend(format_cli_arg(key, value))

        for key, value in asdict(self.pipeline).items():
            command.extend(format_cli_arg(key, value))

        for key, value in asdict(self.training).items():
            if key in TRAINING_SKIP:
                continue
            command.extend(format_cli_arg(key, value))

        gw = self.gw
        command.extend(format_cli_arg("rasterizer", gw.rasterizer))
        command.extend(format_negatable_bool("exposure_compensation", gw.exposure_compensation))
        command.extend(format_negatable_bool("multiview", gw.multiview))
        command.extend(format_cli_arg("multiview_config", gw.multiview_config))
        command.extend(format_cli_arg("multiview_factor", gw.multiview_factor))
        command.extend(format_cli_arg("regularization_from_iter", gw.regularization_from_iter))
        command.extend(format_cli_arg("lambda_depth_normal", gw.lambda_depth_normal))
        command.extend(
            format_negatable_bool("use_max_size_threshold", gw.use_max_size_threshold)
        )
        command.extend(format_cli_arg("normal_field_config", gw.normal_field_config))
        if gw.N_max_gaussians is not None:
            command.extend(format_cli_arg("N_max_gaussians", gw.N_max_gaussians))

        return command
