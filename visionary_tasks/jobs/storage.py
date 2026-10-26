from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from visionary_progress import append_progress_event, read_progress_events

from ..domain.jobs import JobState
from ..workers.contract import WorkerResult


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_job_state(path: Path, state: JobState) -> None:
    write_json(path, state.to_dict())


def read_job_state(path: Path) -> JobState | None:
    data = read_json(path)
    if data is None:
        return None
    return JobState.from_dict(data)


def write_worker_result(path: Path, result: WorkerResult) -> None:
    write_json(path, result.to_dict())


def read_worker_result(path: Path) -> WorkerResult | None:
    data = read_json(path)
    if data is None:
        return None
    return WorkerResult.from_dict(data)


def save_upload_files(files: list[tuple[str, bytes]], input_dir: Path) -> int:
    input_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for filename, content in files:
        sanitized = Path(filename).name
        if not sanitized:
            continue
        (input_dir / sanitized).write_bytes(content)
        count += 1
    return count
