import logging

from ..jobs.models import JobRecord, now_iso
from ..jobs.paths import JobPaths
from ..jobs.storage import read_record, write_record
from ..jobs.stages import StageRecord
from ..settings import Settings
from .pipeline import check_stage_inputs, get_stage

logger = logging.getLogger(__name__)


def run_job(settings: Settings, paths: JobPaths, enabled_stages: list[str]) -> None:
    record = read_record(paths.status_file)
    if record is None:
        raise RuntimeError(f"任务状态文件不存在: {paths.status_file}")
    existing = {stage.name: stage for stage in record.stages}
    record.enabled = list(enabled_stages)
    record.stages = [existing.get(name, StageRecord.pending(name)) for name in enabled_stages]
    write_record(paths.status_file, record)
    current_stage: str | None = None
    try:
        for stage_id in enabled_stages:
            current_stage = stage_id
            spec = get_stage(stage_id)
            missing = check_stage_inputs(spec, paths, settings)
            if missing:
                _set_stage(record, stage_id, "error", error="; ".join(missing))
                write_record(paths.status_file, record)
                return
            _set_stage(record, stage_id, "running")
            write_record(paths.status_file, record)
            artifact = spec.run(settings, paths)
            _set_stage(record, stage_id, "done", artifact=artifact)
            write_record(paths.status_file, record)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", paths.job_id)
        if current_stage is None:
            raise
        _set_stage(record, current_stage, "error", error=str(exc))
        write_record(paths.status_file, record)


def _set_stage(
    record: JobRecord,
    stage_name: str,
    status: str,
    artifact: dict[str, str] | None = None,
    error: str | None = None,
) -> None:
    now = now_iso()
    for stage in record.stages:
        if stage.name == stage_name:
            stage.status = status  # type: ignore[assignment]
            stage.started_at = stage.started_at or now
            stage.ended_at = now if status in {"done", "error", "skipped"} else None
            stage.artifact = artifact if status == "done" else stage.artifact
            stage.error = error if status == "error" else None
            record.updated_at = now
            return
