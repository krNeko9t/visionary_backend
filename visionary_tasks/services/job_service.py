from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..config.loader import deep_merge, materialize_job_configs
from ..domain.input_modes import get_iteration, is_native_3dgs_ply_mode
from ..domain.jobs import JobSpec, JobState, ProgressEvent, now_iso
from ..domain.pipeline import INPUT_MODE_DEFINITIONS, OUTPUT_DEFINITIONS, PRESETS, STAGE_DEFINITIONS
from ..jobs.paths import JobPaths
from ..jobs.storage import read_job_state, read_progress_events, write_job_state
from ..settings import Settings
from .ingest import ingest_job_files
from .planner import plan_pipeline
from .progress import compute_job_progress, derive_current_stage, derive_error, derive_job_status
from .runner import build_initial_stages, run_job


class JobService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_job(
        self,
        spec: JobSpec,
        files: list[tuple[str, bytes]],
    ) -> JobState:
        plan = plan_pipeline(spec)
        job_id = uuid.uuid4().hex[:12]
        paths = JobPaths.from_settings(self.settings, job_id)

        preset = spec.preset
        gs_preset = PRESETS.get(preset, {}).get("gs_preset")
        stage_overrides = _build_stage_overrides(spec)
        gs_config = materialize_job_configs(
            self.settings,
            paths,
            stage_ids=list(plan.stages),
            overrides=stage_overrides,
            preset=gs_preset,
        )
        paths.ensure_layout(gs_config.output_relative)
        ingest_job_files(spec, files, paths, gs_config.output_relative)

        timestamp = now_iso()
        state = JobState(
            job_id=job_id,
            spec=spec,
            status="queued",
            stages=build_initial_stages(list(plan.stages)),
            artifacts=[],
            created_at=timestamp,
            updated_at=timestamp,
            planned_stages=list(plan.stages),
        )
        write_job_state(paths.job_state_file, state)
        return state

    def get_job(self, job_id: str) -> JobState | None:
        paths = JobPaths.from_settings(self.settings, job_id)
        state = read_job_state(paths.job_state_file)
        if state is None:
            return None
        state.status = derive_job_status(state)
        state.current_stage_id = derive_current_stage(state)
        state.error = derive_error(state)
        state.progress = compute_job_progress(state, paths)
        return state

    def list_artifacts(self, job_id: str) -> list:
        state = self.get_job(job_id)
        if state is None:
            return []
        return state.artifacts

    def get_artifact_path(self, job_id: str, artifact_id: str) -> Path | None:
        state = self.get_job(job_id)
        if state is None:
            return None
        artifact = state.artifact_by_id(artifact_id)
        if artifact is None or not artifact.downloadable:
            return None
        paths = JobPaths.from_settings(self.settings, job_id)
        file_path = paths.resolve(artifact.path)
        if not file_path.exists():
            return None
        return file_path

    def list_events(self, job_id: str) -> list[ProgressEvent]:
        paths = JobPaths.from_settings(self.settings, job_id)
        state = read_job_state(paths.job_state_file)
        if state is None:
            return []
        events: list[ProgressEvent] = []
        for stage_id in state.planned_stages:
            events.extend(read_progress_events(paths.stage_events_file(stage_id)))
        events.sort(key=lambda event: event.timestamp)
        return events

    def request_cancel(self, job_id: str) -> JobState | None:
        paths = JobPaths.from_settings(self.settings, job_id)
        state = read_job_state(paths.job_state_file)
        if state is None:
            return None
        if state.status in {"done", "error", "cancelled"}:
            return state
        state.cancel_requested = True
        state.updated_at = now_iso()
        write_job_state(paths.job_state_file, state)
        return state

    def run_job_async(self, job_id: str) -> None:
        paths = JobPaths.from_settings(self.settings, job_id)
        run_job(self.settings, paths)

    @staticmethod
    def capabilities() -> dict[str, Any]:
        return {
            "input_modes": [
                {
                    "id": mode.id,
                    "label": mode.label,
                    "file_types": list(mode.file_types),
                    "allowed_outputs": list(mode.allowed_outputs),
                }
                for mode in INPUT_MODE_DEFINITIONS.values()
            ],
            "outputs": [
                {
                    "id": output.id,
                    "label": output.label,
                    "required_stages": list(output.required_stages),
                    "ply_mode_stages": list(output.ply_mode_stages),
                }
                for output in OUTPUT_DEFINITIONS.values()
            ],
            "presets": [
                {"id": preset_id, **payload} for preset_id, payload in PRESETS.items()
            ],
            "stages": [
                {
                    "id": stage.id,
                    "label": stage.label,
                    "order": stage.order,
                    "depends_on": list(stage.depends_on),
                    "required_artifacts": list(stage.required_artifacts),
                    "inputs": list(stage.input_hints),
                }
                for stage in sorted(STAGE_DEFINITIONS.values(), key=lambda item: item.order)
            ],
        }


def _extract_stage_overrides(spec: JobSpec) -> dict[str, dict[str, Any] | None]:
    if not spec.advanced:
        return {}
    overrides = spec.advanced.get("stage_overrides")
    if not isinstance(overrides, dict):
        return {}
    return {str(key): dict(value) if isinstance(value, dict) else None for key, value in overrides.items()}


def _build_stage_overrides(spec: JobSpec) -> dict[str, dict[str, Any] | None]:
    overrides = _extract_stage_overrides(spec)
    if not is_native_3dgs_ply_mode(spec):
        return overrides

    iteration = get_iteration(spec)
    gs_override = deep_merge(
        {
            "training": {
                "output_iteration": iteration,
                "save_iterations": [iteration],
                "checkpoint_iterations": [iteration],
            }
        },
        overrides.get("3dgs") or {},
    )
    dgs_to_pc_override = deep_merge(
        {"extraction": {"iteration": iteration}},
        overrides.get("3dgs-to-pc") or {},
    )
    merged = dict(overrides)
    merged["3dgs"] = gs_override
    merged["3dgs-to-pc"] = dgs_to_pc_override
    return merged
