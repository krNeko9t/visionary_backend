from __future__ import annotations

import configparser
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_every_gitlink_has_a_submodule_configuration() -> None:
    """Keep Git's submodule index entries and .gitmodules in sync."""
    result = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("repository metadata is unavailable")

    gitlink_paths = {
        line.split("\t", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("160000 ")
    }

    modules = configparser.ConfigParser()
    modules.read(REPOSITORY_ROOT / ".gitmodules")
    configured_paths = {
        modules.get(section, "path")
        for section in modules.sections()
        if section.startswith('submodule "')
    }

    assert gitlink_paths == configured_paths
