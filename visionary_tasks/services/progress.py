from __future__ import annotations

from visionary_progress import StageProgress

from ..domain.jobs import JobState, JobStatus, ProgressEvent, StageState
from ..domain.pipeline import STAGE_DEFINITIONS
from ..jobs.paths import JobPaths
from ..jobs.storage import read_progress_events
from ..stages.progress import configured_progress_steps


def derive_job_status(state: JobState) -> JobStatus:
    if state.cancel_requested and state.status not in {"done", "error"}:
        return "cancelled"
    if not state.stages:
        return "queued"
    if any(stage.status == "error" for stage in state.stages):
        return "error"
    if all(stage.status == "done" for stage in state.stages):
        return "done"
    if any(stage.status == "running" for stage in state.stages):
        return "running"
    return "queued"


def compute_stage_progress(stage: StageState, events: list[ProgressEvent]) -> float:
    view = StageProgress(stage.progress_steps)
    for event in events:
        if event.stage_id == stage.stage_id:
            view.consume(event)
    stage.current_step = view.current_step or stage.current_step
    if stage.status == "done":
        return 1.0
    return view.progress if view.progress is not None else stage.progress


def compute_job_progress(state: JobState, paths: JobPaths) -> float:
    # Populate all stage details from the same read used by the total, even at terminal states.
    for stage in state.stages:
        if not stage.progress_steps:
            stage.progress_steps = configured_progress_steps(stage.stage_id, paths)
        events = read_progress_events(paths.stage_events_file(stage.stage_id))
        stage.progress = compute_stage_progress(stage, events)

    if not state.stages:
        return 0.0

    status = derive_job_status(state)
    if status == "done":
        return 100.0
    if status in {"queued", "cancelled"}:
        return 0.0

    weights = _normalized_weights(state.planned_stages)
    total = 0.0
    for stage in state.stages:
        weight = weights.get(stage.stage_id, 0.0)
        total += weight * stage.progress * 100.0

    if status == "error":
        return min(99.0, total)
    return min(99.0, total)


def project_stage_events(stage: StageState, paths: JobPaths) -> list[ProgressEvent]:
    steps = stage.progress_steps or configured_progress_steps(stage.stage_id, paths)
    view = StageProgress(steps)
    return [
        view.consume(event)
        for event in read_progress_events(paths.stage_events_file(stage.stage_id))
        if event.stage_id == stage.stage_id
    ]


def _normalized_weights(stage_ids: list[str]) -> dict[str, float]:
    raw = {stage_id: STAGE_DEFINITIONS[stage_id].weight for stage_id in stage_ids}
    total = sum(raw.values()) or 1.0
    return {stage_id: value / total for stage_id, value in raw.items()}


def derive_current_stage(state: JobState) -> str | None:
    running = next((stage for stage in state.stages if stage.status == "running"), None)
    return running.stage_id if running else None


def derive_error(state: JobState) -> str | None:
    for stage in state.stages:
        if stage.status == "error":
            return stage.error or f"{stage.stage_id} 失败"
    return state.error
