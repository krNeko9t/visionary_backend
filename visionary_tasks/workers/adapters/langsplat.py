from __future__ import annotations

from pathlib import Path

WORKSPACE = "/workspace"

# 只覆盖 Python 源码；submodules 仍用镜像内已编译扩展。
LIVE_CODE_FILES = (
    "train.py",
    "preprocess.py",
    "export_lsv2_final_product.py",
)
LIVE_CODE_DIRS = (
    "scene",
    "eval",
    "utils",
    "arguments",
)


def build_langsplat_live_code_volumes(host_repo: str | Path) -> dict[str, dict[str, str]]:
    repo = Path(host_repo)
    volumes: dict[str, dict[str, str]] = {}
    for name in LIVE_CODE_FILES:
        source = repo / name
        if source.is_file():
            volumes[str(source)] = {"bind": f"{WORKSPACE}/{name}", "mode": "ro"}
    for name in LIVE_CODE_DIRS:
        source = repo / name
        if source.is_dir():
            volumes[str(source)] = {"bind": f"{WORKSPACE}/{name}", "mode": "ro"}
    return volumes
