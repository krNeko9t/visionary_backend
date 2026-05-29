from ..jobs.paths import JobPaths
from ..settings import Settings

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


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
    checkpoint = paths.gs_checkpoint(settings)
    if not checkpoint.exists():
        missing.append(
            f"缺少 3DGS checkpoint: {checkpoint.relative_to(paths.root)}"
        )
    return missing


def missing_gaussian_wrapping_inputs(paths: JobPaths, settings: Settings) -> list[str]:
    missing: list[str] = []
    if not (paths.colmap_dir / "sparse").exists():
        missing.append("缺少 COLMAP 稀疏重建: colmap/sparse")
    gs_ply = paths.gs_output_ply(settings)
    if not gs_ply.exists():
        missing.append(f"缺少 3DGS 点云: {gs_ply.relative_to(paths.root)}")
    return missing
