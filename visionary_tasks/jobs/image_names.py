from __future__ import annotations

import re
from pathlib import Path

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def ascii_image_filenames(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    used: set[str] = set()
    renamed: list[tuple[str, bytes]] = []
    for index, (filename, content) in enumerate(files, start=1):
        name = _ascii_name(filename, index, used)
        used.add(name.lower())
        renamed.append((name, content))
    return renamed


def _ascii_name(filename: str, index: int, used: set[str]) -> str:
    original = Path(filename).name
    suffix = Path(original).suffix.lower()
    if suffix not in _IMAGE_SUFFIXES:
        suffix = ".png"
    if _SAFE_FILENAME.fullmatch(original) and original.lower() not in used:
        return original
    candidate_index = index
    while True:
        candidate = f"img_{candidate_index:04d}{suffix}"
        if candidate.lower() not in used:
            return candidate
        candidate_index += 1
