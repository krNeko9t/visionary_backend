from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path


def zip_directory(source_dir: Path) -> Path:
    """Pack a directory into a temporary zip file.

    Caller is responsible for deleting the returned path after the response
    has been sent (e.g. via BackgroundTasks).
    """
    if not source_dir.is_dir():
        raise ValueError(f"not a directory: {source_dir}")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    zip_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(source_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(source_dir).as_posix())
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise
    return zip_path
