import subprocess

from ..config.loader import load_gs_job_config
from ..jobs.paths import JobPaths
from ..jobs.stage_artifacts import persist_stage_artifact
from ..orchestration.inputs import missing_3dgs_inputs
from ..settings import Settings


def run(settings: Settings, paths: JobPaths) -> dict[str, str]:
    missing = missing_3dgs_inputs(paths, settings)
    if missing:
        raise FileNotFoundError(missing[0])

    config = load_gs_job_config(settings, paths)
    source_dir = paths.colmap_dir
    command = config.to_train_command(
        str(source_dir),
        str(paths.output_dir(settings)),
    )
    subprocess.run(
        command,
        cwd=settings.gs_repo_path,
        check=True,
    )
    ply = paths.gs_output_ply(settings, config.output_iteration)
    if not ply.exists():
        raise FileNotFoundError(f"找不到 3DGS 输出文件: {ply}")
    return persist_stage_artifact(
        paths,
        "3dgs",
        {"ply": str(ply.relative_to(paths.root))},
    )
