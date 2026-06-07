from __future__ import annotations

from ..domain.jobs import JobState, JobStatus, ProgressEvent, StageState
from ..domain.pipeline import STAGE_DEFINITIONS
from ..jobs.paths import JobPaths
from ..jobs.storage import read_progress_events


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
    stage_events = [event for event in events if event.stage_id == stage.stage_id]
    progress_values = [
        event.progress for event in stage_events if event.progress is not None
    ]
    if progress_values:
        return max(0.0, min(1.0, progress_values[-1]))
    if stage.status == "done":
        return 1.0
    if stage.status == "running":
        return 0.0
    return 0.0


def compute_job_progress(state: JobState, paths: JobPaths) -> float:
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
        events = read_progress_events(paths.stage_events_file(stage.stage_id))
        stage_progress = compute_stage_progress(stage, events)
        total += weight * stage_progress * 100.0

    if status == "error":
        return min(99.0, total)
    return min(99.0, total)


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
