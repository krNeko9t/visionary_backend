from __future__ import annotations

import logging

from ..domain.jobs import JobState, StageState, now_iso
from ..jobs.paths import JobPaths
from ..jobs.storage import read_job_state, write_job_state
from ..settings import Settings
from ..stages.registry import check_stage_inputs, get_stage_runner
from .progress import compute_job_progress, derive_current_stage, derive_error, derive_job_status

logger = logging.getLogger(__name__)


def run_job(settings: Settings, paths: JobPaths) -> None:
    state = read_job_state(paths.job_state_file)
    if state is None:
        raise RuntimeError(f"任务状态文件不存在: {paths.job_state_file}")

    if state.cancel_requested:
        state.status = "cancelled"
        state.updated_at = now_iso()
        write_job_state(paths.job_state_file, state)
        return

    current_stage_id: str | None = None
    try:
        for stage_id in state.planned_stages:
            if _is_cancelled(paths):
                return

            current_stage_id = stage_id
            missing = check_stage_inputs(stage_id, paths, settings)
            if missing:
                _set_stage(state, stage_id, "error", error="; ".join(missing))
                _refresh_state(state, paths)
                return

            _set_stage(state, stage_id, "running")
            _refresh_state(state, paths)

            runner = get_stage_runner(stage_id)
            result = runner(settings, paths)
            if result.status == "error":
                _set_stage(state, stage_id, "error", error=result.error or f"{stage_id} 失败")
                _refresh_state(state, paths)
                return

            _set_stage(state, stage_id, "done", progress=1.0)
            _merge_artifacts(state, result.artifacts)
            _refresh_state(state, paths)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", paths.job_id)
        if current_stage_id is None:
            raise
        _set_stage(state, current_stage_id, "error", error=str(exc))
        _refresh_state(state, paths)


def _is_cancelled(paths: JobPaths) -> bool:
    state = read_job_state(paths.job_state_file)
    if state is None:
        return False
    if state.cancel_requested:
        state.status = "cancelled"
        state.updated_at = now_iso()
        write_job_state(paths.job_state_file, state)
        return True
    return False


def _set_stage(
    state: JobState,
    stage_id: str,
    status: str,
    *,
    progress: float = 0.0,
    error: str | None = None,
) -> None:
    now = now_iso()
    for stage in state.stages:
        if stage.stage_id == stage_id:
            stage.status = status  # type: ignore[assignment]
            stage.started_at = stage.started_at or now
            stage.ended_at = now if status in {"done", "error", "skipped", "cancelled"} else None
            stage.progress = progress if status == "done" else stage.progress
            stage.error = error if status == "error" else None
            state.updated_at = now
            return


def _merge_artifacts(state: JobState, artifacts: list) -> None:
    existing = {artifact.id: artifact for artifact in state.artifacts}
    for artifact in artifacts:
        existing[artifact.id] = artifact
    state.artifacts = list(existing.values())


def _refresh_state(state: JobState, paths: JobPaths) -> None:
    state.status = derive_job_status(state)
    state.current_stage_id = derive_current_stage(state)
    state.error = derive_error(state)
    state.progress = compute_job_progress(state, paths)
    state.updated_at = now_iso()
    write_job_state(paths.job_state_file, state)


def build_initial_stages(stage_ids: list[str]) -> list[StageState]:
    return [StageState.pending(stage_id) for stage_id in stage_ids]
