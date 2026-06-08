from __future__ import annotations

from ..domain.input_modes import get_input_mode, is_native_3dgs_ply_mode
from ..domain.jobs import JobSpec
from ..domain.pipeline import (
    INPUT_MODE_DEFINITIONS,
    KNOWN_OUTPUT_IDS,
    KNOWN_STAGE_IDS,
    OUTPUT_DEFINITIONS,
    PLY_MODE_STAGE_ARTIFACTS,
    PRESETS,
    STAGE_DEFINITIONS,
    PipelinePlan,
)


def plan_pipeline(spec: JobSpec) -> PipelinePlan:
    if not spec.outputs:
        raise ValueError("spec.outputs 不能为空")

    input_mode = get_input_mode(spec)
    input_mode_def = INPUT_MODE_DEFINITIONS[input_mode]

    unknown_outputs = [item for item in spec.outputs if item not in KNOWN_OUTPUT_IDS]
    if unknown_outputs:
        raise ValueError(f"未知输出类型: {', '.join(unknown_outputs)}")

    disallowed = [item for item in spec.outputs if item not in input_mode_def.allowed_outputs]
    if disallowed:
        raise ValueError(
            f"input_mode={input_mode} 不支持输出类型: {', '.join(disallowed)}"
        )

    if spec.preset not in PRESETS:
        raise ValueError(f"未知 preset: {spec.preset}")

    outputs = list(spec.outputs)
    if spec.options.get("language_features") and "language_model" not in outputs:
        if input_mode != "images":
            raise ValueError("language_features 仅支持 input_mode=images")
        outputs.append("language_model")

    stage_set: set[str] = set()
    if is_native_3dgs_ply_mode(spec):
        for output_id in outputs:
            output_def = OUTPUT_DEFINITIONS[output_id]
            stage_set.update(output_def.ply_mode_stages or output_def.required_stages)
    else:
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
    if is_native_3dgs_ply_mode(spec):
        _validate_ply_mode_stages(ordered)
    else:
        _validate_stage_dependencies(ordered)
    return PipelinePlan(outputs=tuple(outputs), stages=tuple(ordered))


def _validate_stage_dependencies(stage_ids: list[str]) -> None:
    enabled = set(stage_ids)
    for stage_id in stage_ids:
        definition = STAGE_DEFINITIONS[stage_id]
        missing = [dep for dep in definition.depends_on if dep not in enabled]
        if missing:
            raise ValueError(
                f"阶段 {stage_id} 依赖 {', '.join(missing)}，但当前计划未包含这些阶段"
            )


def _validate_ply_mode_stages(stage_ids: list[str]) -> None:
    allowed = set(PLY_MODE_STAGE_ARTIFACTS)
    unknown = [stage_id for stage_id in stage_ids if stage_id not in allowed]
    if unknown:
        raise ValueError(
            f"native_3dgs_ply 模式仅支持阶段: {', '.join(sorted(allowed))}"
        )
