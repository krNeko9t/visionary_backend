import json
import shutil
from pathlib import Path
from typing import Any, Callable

from .models import JobRecord


def write_record(path: Path, record: JobRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_record(path: Path) -> JobRecord | None:
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return JobRecord.from_dict(data)


def update_record(path: Path, updater: Callable[[JobRecord], JobRecord]) -> JobRecord:
    record = read_record(path)
    if record is None:
        raise FileNotFoundError(f"任务状态文件不存在: {path}")
    updated = updater(record)
    if not isinstance(updated, JobRecord):
        raise TypeError("updater 必须返回 JobRecord")
    write_record(path, updated)
    return updated


def save_upload_files(files: list[tuple[str, bytes]], input_dir: Path) -> int:
    count = 0
    for filename, content in files:
        sanitized = Path(filename).name
        if not sanitized:
            continue
        (input_dir / sanitized).write_bytes(content)
        count += 1
    return count


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
