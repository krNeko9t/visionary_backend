from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def run_subprocess_worker(
    *,
    command: list[str],
    cwd: Path,
    label: str = "worker",
) -> None:
    logger.info("启动 %s: %s", label, " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)
