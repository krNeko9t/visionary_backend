from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .cli import format_cli_arg

MODEL_SHORTHAND = {
    "resolution": "-r",
    "white_background": "-w",
    "images": "-i",
    "feature_level": "-f",
}
MODEL_SKIP = {"source_path", "model_path"}
TRAINING_SKIP = {"start_checkpoint"}


@dataclass
class LangSplatRuntimeConfig:
    worker_image: str = "langsplatv2:pt241"
    model_relative: str = "langsplatv2"
    ckpts_host: str = ""


@dataclass
class LangSplatPreprocessConfig:
    resolution: int = -1
    sam_ckpt_path: str = "ckpts/sam_vit_h_4b8939.pth"


@dataclass
class LangSplatModelConfig:
    sh_degree: int = 3
    language_features_name: str = "language_features"
    images: str = "images"
    resolution: int = -1
    white_background: bool = False
    feature_level: int = 0
    data_device: str = "cuda"
    eval: bool = False


@dataclass
class LangSplatOptimizationConfig:
    iterations: int = 30_000
    position_lr_init: float = 0.00016
    position_lr_final: float = 0.0000016
    position_lr_delay_mult: float = 0.01
    position_lr_max_steps: int = 30_000
    feature_lr: float = 0.0025
    opacity_lr: float = 0.05
    language_feature_lr: float = 0.0025
    include_feature: bool = True
    quick_render: bool = False
    vq_layer_num: int = 1
    codebook_size: int = 64
    scaling_lr: float = 0.005
    rotation_lr: float = 0.001
    percent_dense: float = 0.01
    lambda_dssim: float = 0.2
    densification_interval: int = 100
    opacity_reset_interval: int = 3000
    densify_from_iter: int = 500
    densify_until_iter: int = 15_000
    densify_grad_threshold: float = 0.0002


@dataclass
class LangSplatPipelineConfig:
    convert_SHs_python: bool = False
    compute_cov3D_python: bool = False
    debug: bool = False


@dataclass
class LangSplatTrainingConfig:
    test_iterations: list[int] = field(
        default_factory=lambda: [2000, 4000, 6000, 8000, 10_000, 30_000]
    )
    save_iterations: list[int] = field(
        default_factory=lambda: [2000, 4000, 6000, 8000, 10_000, 30_000]
    )
    checkpoint_iterations: list[int] = field(
        default_factory=lambda: [2000, 4000, 6000, 8000, 10_000, 30_000]
    )
    cos_loss: bool = True
    l1_loss: bool = False
    normalize: bool = False
    accum_iter: int = 1
    topk: int = 4
    quiet: bool = False
    ip: str = "127.0.0.1"
    port: int = 55557
    debug_from: int = -1
    detect_anomaly: bool = False
    start_checkpoint: str | None = None


@dataclass
class LangSplatJobConfig:
    runtime: LangSplatRuntimeConfig
    preprocess: LangSplatPreprocessConfig
    model: LangSplatModelConfig
    optimization: LangSplatOptimizationConfig
    pipeline: LangSplatPipelineConfig
    training: LangSplatTrainingConfig

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> "LangSplatJobConfig":
        return cls(
            runtime=LangSplatRuntimeConfig(**dict(payload.get("runtime") or {})),
            preprocess=LangSplatPreprocessConfig(**dict(payload.get("preprocess") or {})),
            model=LangSplatModelConfig(**dict(payload.get("model") or {})),
            optimization=LangSplatOptimizationConfig(**dict(payload.get("optimization") or {})),
            pipeline=LangSplatPipelineConfig(**dict(payload.get("pipeline") or {})),
            training=LangSplatTrainingConfig(**dict(payload.get("training") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime": asdict(self.runtime),
            "preprocess": asdict(self.preprocess),
            "model": asdict(self.model),
            "optimization": asdict(self.optimization),
            "pipeline": asdict(self.pipeline),
            "training": asdict(self.training),
        }

    def to_preprocess_command(self, dataset_path: str) -> list[str]:
        command = ["python", "preprocess.py", "--dataset_path", dataset_path]
        for key, value in asdict(self.preprocess).items():
            if key == "dataset_path":
                continue
            command.extend(format_cli_arg(key, value))
        return command

    def to_train_command(
        self,
        source_path: str,
        model_path: str,
        checkpoint_path: str,
    ) -> list[str]:
        command = [
            "python",
            "train.py",
            "-s",
            source_path,
            "-m",
            model_path,
            "--start_checkpoint",
            checkpoint_path,
        ]
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
        return command
