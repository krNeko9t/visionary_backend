from __future__ import annotations

from ..domain.jobs import JobSpec
from ..domain.pipeline import (
    KNOWN_OUTPUT_IDS,
    KNOWN_STAGE_IDS,
    OUTPUT_DEFINITIONS,
    PRESETS,
    STAGE_DEFINITIONS,
    PipelinePlan,
)


def plan_pipeline(spec: JobSpec) -> PipelinePlan:
    if not spec.outputs:
        raise ValueError("spec.outputs 不能为空")

    unknown_outputs = [item for item in spec.outputs if item not in KNOWN_OUTPUT_IDS]
    if unknown_outputs:
        raise ValueError(f"未知输出类型: {', '.join(unknown_outputs)}")

    if spec.preset not in PRESETS:
        raise ValueError(f"未知 preset: {spec.preset}")

    outputs = list(spec.outputs)
    if spec.options.get("language_features") and "language_model" not in outputs:
        outputs.append("language_model")

    stage_set: set[str] = set()
    for output_id in outputs:
        for stage_id in OUTPUT_DEFINITIONS[output_id].required_stages:
            stage_set.add(stage_id)

    if spec.advanced and spec.advanced.get("stages"):
        advanced_stages = [str(item) for item in spec.advanced["stages"]]
        unknown_stages = [item for item in advanced_stages if item not in KNOWN_STAGE_IDS]
        if unknown_stages:
            raise ValueError(f"未知阶段: {', '.join(unknown_stages)}")
        if not advanced_stages:
            raise ValueError("advanced.stages 不能为空")
        stage_set = set(advanced_stages)

    ordered = sorted(stage_set, key=lambda stage_id: STAGE_DEFINITIONS[stage_id].order)
    _validate_dependencies(ordered)
    return PipelinePlan(outputs=tuple(outputs), stages=tuple(ordered))


def _validate_dependencies(stage_ids: list[str]) -> None:
    enabled = set(stage_ids)
    for stage_id in stage_ids:
        definition = STAGE_DEFINITIONS[stage_id]
        missing = [dep for dep in definition.depends_on if dep not in enabled]
        if missing:
            raise ValueError(
                f"阶段 {stage_id} 依赖 {', '.join(missing)}，但当前计划未包含这些阶段"
            )
