from pathlib import Path

import pytest

from visionary_tasks.config.loader import load_yaml, materialize_stage_config
from visionary_tasks.config.registry import default_config_path, stage_preset_paths
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.settings.gw_train import GwTrainJobConfig


def test_gw_train_presets_are_discovered():
    assert set(stage_preset_paths("gw-train")) == {"small", "mid", "high"}


def test_gw_train_default_yaml_loads():
    config = GwTrainJobConfig.from_merged_dict(load_yaml(default_config_path("gw-train")))
    assert config.gw.rasterizer == "ours"
    assert config.training.output_iteration == 30_000


def test_gw_train_requires_iterations_alignment():
    with pytest.raises(ValueError, match="optimization.iterations"):
        GwTrainJobConfig.from_merged_dict(
            {
                "optimization": {"iterations": 12000},
                "training": {
                    "output_iteration": 30000,
                    "save_iterations": [30000],
                    "checkpoint_iterations": [30000],
                },
            }
        )


def test_gw_train_to_train_command(tmp_path: Path):
    job_id = "gw-train-command"
    paths = JobPaths(job_id=job_id, root=tmp_path / job_id)
    paths.root.mkdir(parents=True)
    config = materialize_stage_config("gw-train", paths, preset="small")
    assert isinstance(config, GwTrainJobConfig)

    command = config.to_train_command("/job/colmap", "/job/output")

    assert command[:6] == [
        "python",
        "gaussian_wrapping/train.py",
        "-s",
        "/job/colmap",
        "-m",
        "/job/output",
    ]
    assert command[command.index("--iterations") + 1] == "12000"
    assert "--rasterizer" in command
    assert "ours" in command
