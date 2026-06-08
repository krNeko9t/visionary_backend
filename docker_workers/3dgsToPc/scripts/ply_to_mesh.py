#!/usr/bin/env python3
"""Task worker entry: native 3DGS PLY → Poisson mesh (no COLMAP)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from gs_to_pc.ply_only import PlyOnlySettings, run_ply_to_mesh


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert native 3DGS PLY to mesh via dense point cloud + Poisson.")
    parser.add_argument("--input_path", required=True, type=str)
    parser.add_argument("--mesh_output_path", required=True, type=str)
    parser.add_argument("--num_points", type=int, default=5_000_000)
    parser.add_argument("--mahalanobis_distance_std", type=float, default=2.0)
    parser.add_argument("--min_opacity", type=float, default=0.05)
    parser.add_argument("--cull_gaussian_sizes", type=float, default=0.0)
    parser.add_argument("--max_sh_degree", type=int, default=3)
    parser.add_argument("--exact_num_points", action="store_true")
    parser.add_argument("--clean_pointcloud", action="store_true", default=True)
    parser.add_argument("--no_clean_pointcloud", action="store_true")
    parser.add_argument("--poisson_depth", type=int, default=10)
    parser.add_argument("--laplacian_iterations", type=int, default=10)
    parser.add_argument("--bounding_box_min", nargs=3, type=float, default=None)
    parser.add_argument("--bounding_box_max", nargs=3, type=float, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.min_opacity < 0 or args.min_opacity > 1:
        raise ValueError("min_opacity must be between 0 and 1")
    if args.mahalanobis_distance_std <= 0:
        raise ValueError("mahalanobis_distance_std must be > 0")
    if args.num_points <= 0:
        raise ValueError("num_points must be > 0")
    if args.cull_gaussian_sizes < 0 or args.cull_gaussian_sizes > 1:
        raise ValueError("cull_gaussian_sizes must be between 0 and 1")

    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    clean_pointcloud = args.clean_pointcloud and not args.no_clean_pointcloud

    settings = PlyOnlySettings(
        num_points=args.num_points,
        mahalanobis_distance_std=args.mahalanobis_distance_std,
        min_opacity=args.min_opacity,
        bounding_box_min=list(args.bounding_box_min) if args.bounding_box_min is not None else None,
        bounding_box_max=list(args.bounding_box_max) if args.bounding_box_max is not None else None,
        cull_large_percentage=args.cull_gaussian_sizes,
        max_sh_degree=args.max_sh_degree,
        exact_num_points=args.exact_num_points,
        clean_pointcloud=clean_pointcloud,
        poisson_depth=args.poisson_depth,
        laplacian_iterations=args.laplacian_iterations,
        quiet=args.quiet,
        device="cuda:0" if torch.cuda.is_available() else "cpu",
    )

    run_ply_to_mesh(args.input_path, args.mesh_output_path, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
