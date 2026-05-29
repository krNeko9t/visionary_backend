import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LangSplatSettings:
    worker_image: str
    model_relative: str
    ckpts_host: str
    feature_level: int
    vq_layer_num: int
    codebook_size: int
    topk: int
    cos_loss: bool

    @classmethod
    def from_env(cls) -> "LangSplatSettings":
        return cls(
            worker_image=os.getenv("LANGSPLAT_WORKER_IMAGE", "langsplatv2:pt241"),
            model_relative=os.getenv("LANGSPLAT_MODEL_RELATIVE", "langsplatv2"),
            ckpts_host=os.getenv(
                "LANGSPLAT_CKPTS_HOST",
                r"C:\Visionary\data\ckpts",
            ).strip(),
            feature_level=int(os.getenv("LANGSPLAT_FEATURE_LEVEL", "0")),
            vq_layer_num=int(os.getenv("LANGSPLAT_VQ_LAYER_NUM", "1")),
            codebook_size=int(os.getenv("LANGSPLAT_CODEBOOK_SIZE", "64")),
            topk=int(os.getenv("LANGSPLAT_TOPK", "4")),
            cos_loss=_env_bool("LANGSPLAT_COS_LOSS", True),
        )

    def preprocess_command(self, dataset_path: str) -> list[str]:
        return [
            "python",
            "preprocess.py",
            "--dataset_path",
            dataset_path,
        ]

    def train_command(
        self,
        source_path: str,
        model_path: str,
        checkpoint_path: str,
    ) -> list[str]:
        cmd = [
            "python",
            "train.py",
            "-s",
            source_path,
            "-m",
            model_path,
            "--start_checkpoint",
            checkpoint_path,
            "--feature_level",
            str(self.feature_level),
            "--vq_layer_num",
            str(self.vq_layer_num),
            "--codebook_size",
            str(self.codebook_size),
            "--topk",
            str(self.topk),
        ]
        if self.cos_loss:
            cmd.append("--cos_loss")
        return cmd
