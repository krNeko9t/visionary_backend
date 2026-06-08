from __future__ import annotations

from .jobs import JobSpec

INPUT_MODE_IMAGES = "images"
INPUT_MODE_NATIVE_3DGS_PLY = "native_3dgs_ply"
KNOWN_INPUT_MODES = frozenset({INPUT_MODE_IMAGES, INPUT_MODE_NATIVE_3DGS_PLY})

DEFAULT_ITERATION = 30_000


def get_input_mode(spec: JobSpec) -> str:
    mode = str(spec.options.get("input_mode", INPUT_MODE_IMAGES))
    if mode not in KNOWN_INPUT_MODES:
        raise ValueError(f"未知 input_mode: {mode}")
    return mode


def get_iteration(spec: JobSpec) -> int:
    raw = spec.options.get("iteration", DEFAULT_ITERATION)
    iteration = int(raw)
    if iteration <= 0:
        raise ValueError("options.iteration 必须是正整数")
    return iteration


def is_native_3dgs_ply_mode(spec: JobSpec) -> bool:
    return get_input_mode(spec) == INPUT_MODE_NATIVE_3DGS_PLY
