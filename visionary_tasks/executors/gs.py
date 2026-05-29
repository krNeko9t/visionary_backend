import subprocess

from ..jobs.paths import JobPaths
from ..jobs.stage_artifacts import persist_stage_artifact
from ..orchestration.inputs import missing_3dgs_inputs
from ..settings import Settings


def run(settings: Settings, paths: JobPaths) -> dict[str, str]:
    missing = missing_3dgs_inputs(paths, settings)
    if missing:
        raise FileNotFoundError(missing[0])
    source_dir = paths.colmap_dir

    command = [
        "python",
        "train.py",
        "-s",
        str(source_dir),
        "-m",
        str(paths.output_dir(settings)),
        "--iterations",
        str(settings.gs_iterations),
        "--save_iterations",
        str(settings.gs_save_iteration),
        # 与 paths.gs_checkpoint / langsplat --start_checkpoint 对齐(train.py 写入 chkpnt{iter}.pth)
        "--checkpoint_iterations",
        str(settings.gs_save_iteration),
    ]
    subprocess.run(
        command,
        cwd=settings.gs_repo_path,
        check=True,
    )
    ply = paths.gs_output_ply(settings)
    if not ply.exists():
        raise FileNotFoundError(f"找不到 3DGS 输出文件: {ply}")
    return persist_stage_artifact(
        paths,
        "3dgs",
        {"ply": str(ply.relative_to(paths.root))},
    )
