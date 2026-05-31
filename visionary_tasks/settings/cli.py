from __future__ import annotations

from typing import Any


def format_cli_arg(
    key: str,
    value: Any,
    *,
    shorthand: str | None = None,
) -> list[str]:
    flag = shorthand or f"--{key}"

    if value is None:
        return []

    if isinstance(value, bool):
        return [flag] if value else []

    if isinstance(value, list):
        if not value:
            return []
        return [flag, *[str(item) for item in value]]

    if isinstance(value, str) and not value:
        return []

    return [flag, str(value)]


def format_negatable_bool(
    key: str,
    value: bool,
    *,
    true_flag: str | None = None,
    false_flag: str | None = None,
) -> list[str]:
    if value:
        return [true_flag or f"--{key}"]
    return [false_flag or f"--no_{key}"]
