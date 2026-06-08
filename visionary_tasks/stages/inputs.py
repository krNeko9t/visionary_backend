from ..config.loader import load_gs_job_config
from ..domain.input_modes import get_iteration
from ..jobs.paths import JobPaths
from ..jobs.storage import read_job_state
from ..jobs.ply_validation import validate_native_3dgs_ply
from ..settings import Settings

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _job_spec(paths: JobPaths):
    state = read_job_state(paths.job_state_file)
    if state is None:
        return None
    return state.spec


def missing_colmap_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    del settings
    images = [
        path
        for path in paths.input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if images:
        return []
    return ["缺少输入图像: input/ 下需有 jpg/png 等图片"]


def missing_3dgs_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    del settings
    sparse = paths.colmap_dir / "sparse"
    if sparse.exists():
        return []
    return ["缺少 COLMAP 稀疏重建: colmap/sparse"]


def missing_langsplat_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    missing: list[str] = []
    if not (paths.colmap_dir / "sparse").exists():
        missing.append("缺少 COLMAP 稀疏重建: colmap/sparse")
    config = load_gs_job_config(settings, paths)
    checkpoint = paths.gs_checkpoint(config.output_relative, config.output_iteration)
    if not checkpoint.exists():
        missing.append(f"缺少 3DGS checkpoint: {checkpoint.relative_to(paths.root)}")
    return missing


def missing_gaussian_wrapping_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    return _missing_gaussian_wrapping_full_inputs(paths, settings)


def missing_3dgs_to_pc_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    return _missing_3dgs_to_pc_ply_inputs(paths, settings)


def _missing_gaussian_wrapping_full_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    missing: list[str] = []
    if not (paths.colmap_dir / "sparse").exists():
        missing.append("缺少 COLMAP 稀疏重建: colmap/sparse")
    config = load_gs_job_config(settings, paths)
    gs_ply = paths.gs_output_ply(config.output_relative, config.output_iteration)
    if not gs_ply.exists():
        missing.append(f"缺少 3DGS 点云: {gs_ply.relative_to(paths.root)}")
    return missing


def _missing_3dgs_to_pc_ply_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    spec = _job_spec(paths)
    if spec is None:
        return ["缺少任务规格"]
    config = load_gs_job_config(settings, paths)
    iteration = get_iteration(spec)
    gs_ply = paths.gs_output_ply(config.output_relative, iteration)
    if not gs_ply.exists():
        return [f"缺少 3DGS 点云: {gs_ply.relative_to(paths.root)}"]
    try:
        validate_native_3dgs_ply(gs_ply.read_bytes())
    except ValueError as exc:
        return [str(exc)]
    return []
