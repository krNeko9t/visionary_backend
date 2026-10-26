from __future__ import annotations

from visionary_progress import StepDefinition

from ..config.loader import load_yaml
from ..jobs.paths import JobPaths
from ..settings.langsplat import LangSplatJobConfig


def langsplat_progress_steps(config: LangSplatJobConfig) -> list[StepDefinition]:
    levels = config.training_feature_levels()
    return [
        StepDefinition({"name": "preprocess"}, "预处理", 0.3),
        *[
            StepDefinition({"name": "train", "level": level}, f"训练 level={level}", 0.5 / len(levels))
            for level in levels
        ],
        StepDefinition({"name": "export"}, "导出", 0.2),
    ]


def configured_progress_steps(stage_id: str, paths: JobPaths) -> list[StepDefinition]:
    if stage_id != "langsplat":
        return []
    path = paths.stage_config_path(stage_id)
    if not path.exists():
        return []  # Historical jobs with no configuration still use stage milestones.
    return langsplat_progress_steps(LangSplatJobConfig.from_merged_dict(load_yaml(path)))
