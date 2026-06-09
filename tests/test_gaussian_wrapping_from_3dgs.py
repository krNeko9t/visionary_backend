from pathlib import Path

from visionary_tasks.config.loader import load_yaml, materialize_stage_config
from visionary_tasks.config.registry import default_config_path
from visionary_tasks.jobs.paths import JobPaths
from visionary_tasks.settings.gaussian_wrapping import GaussianWrappingJobConfig
from visionary_tasks.stages.gaussian_wrapping.build_extract_command import (
    build_extract_command,
)
from visionary_tasks.stages.gaussian_wrapping.resolve_3dgs_output_for_extract import (
    ExtractInputs,
    resolve,
)


def _gs_config(tmp_path: Path, output_iteration: int = 42_000):
    from visionary_tasks.settings.gs import GsJobConfig

    job_id = "gw-from-3dgs"
    paths = JobPaths(job_id=job_id, root=tmp_path / job_id)
    paths.root.mkdir(parents=True)
    config = materialize_stage_config(
        "3dgs",
        paths,
        override={
            "training": {
                "output_iteration": output_iteration,
                "save_iterations": [output_iteration],
                "checkpoint_iterations": [output_iteration],
            }
        },
    )
    assert isinstance(config, GsJobConfig)
    return config


def test_default_yaml_has_no_upstream_fields():
    payload = load_yaml(default_config_path("gaussian-wrapping"))
    extraction = payload["extraction"]
    assert "iteration" not in extraction
    assert "resolution" not in extraction


def test_resolve_reads_3dgs_output_iteration(tmp_path: Path):
    gs = _gs_config(tmp_path, output_iteration=42_000)
    paths = JobPaths(job_id="gw-from-3dgs", root=tmp_path / "gw-from-3dgs")

    upstream = resolve(paths, gs)

    assert upstream == ExtractInputs(
        colmap_path="/job/colmap",
        model_path="/job/output",
        iteration=42_000,
    )


def test_build_extract_command_uses_upstream_iteration(tmp_path: Path):
    job_id = "gw-command"
    paths = JobPaths(job_id=job_id, root=tmp_path / job_id)
    paths.root.mkdir(parents=True)
    config = materialize_stage_config("gaussian-wrapping", paths)
    assert isinstance(config, GaussianWrappingJobConfig)
    assert not hasattr(config.extraction, "iteration")

    upstream = ExtractInputs(
        colmap_path="/job/colmap",
        model_path="/job/output",
        iteration=30_000,
    )
    command = build_extract_command(config, upstream)

    assert command[0:7] == [
        "python",
        "gaussian_wrapping/scripts/extract_and_texture_from_native_3dgs.py",
        "-s",
        "/job/colmap",
        "-m",
        "/job/output",
        "--iteration",
    ]
    assert command[7] == "30000"
    assert "-r" not in command


def test_from_merged_dict_strips_legacy_extraction_fields():
    config = GaussianWrappingJobConfig.from_merged_dict(
        {
            "extraction": {
                "iteration": 500,
                "resolution": -1,
                "n_pivots": 3,
            }
        }
    )
    assert config.extraction.n_pivots == 3
