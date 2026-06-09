from __future__ import annotations

from ...settings.cli import format_cli_arg, format_negatable_bool
from ...settings.gaussian_wrapping import EXTRACT_SCRIPT, GaussianWrappingJobConfig
from .resolve_3dgs_output_for_extract import ExtractInputs


def build_extract_command(
    config: GaussianWrappingJobConfig,
    upstream: ExtractInputs,
) -> list[str]:
    command = [
        "python",
        EXTRACT_SCRIPT,
        "-s",
        upstream.colmap_path,
        "-m",
        upstream.model_path,
        "--iteration",
        str(upstream.iteration),
    ]
    ext = config.extraction
    command.extend(
        [
            "--rasterizer",
            ext.rasterizer,
            "--sdf_mode",
            ext.sdf_mode,
            "--n_pivots",
            str(ext.n_pivots),
            "--n_binary_steps",
            str(ext.n_binary_steps),
            "--isosurface_value",
            str(ext.isosurface_value),
            "--dtype",
            ext.dtype,
        ]
    )
    command.extend(format_negatable_bool("use_valid_mask", ext.use_valid_mask))
    command.extend(format_negatable_bool("postprocess", ext.postprocess))
    command.extend(format_negatable_bool("filter_large_edges", ext.filter_large_edges))
    if ext.mesh:
        command.extend(["--mesh", ext.mesh])
    command.extend(format_cli_arg("texture_n_iter", config.texture.texture_n_iter))
    command.extend(format_cli_arg("texture_lr", config.texture.texture_lr))
    command.extend(format_cli_arg("texture_lambda_dssim", config.texture.texture_lambda_dssim))
    command.extend(format_cli_arg("texture_sh_degree", config.texture.texture_sh_degree))
    if config.decimation.apply_decimation:
        command.append("--apply_decimation")
        command.extend(format_cli_arg("decimate_ratio", config.decimation.decimate_ratio))
    if not config.texture_enabled:
        command.append("--extraction_only")
    return command
