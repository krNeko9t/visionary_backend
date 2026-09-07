#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import logging
import os
import shutil
import struct
from argparse import ArgumentParser, Namespace

MATCHER_COMMANDS = {
    "exhaustive": "exhaustive_matcher",
    "sequential": "sequential_matcher",
}


def _parser() -> ArgumentParser:
    parser = ArgumentParser("Colmap converter")
    parser.add_argument("--no_gpu", action="store_true")
    parser.add_argument("--skip_matching", action="store_true")
    parser.add_argument("--source_path", "-s", required=True, type=str)
    parser.add_argument("--camera", default="OPENCV", type=str)
    parser.add_argument("--matcher", default="exhaustive", type=str, choices=sorted(MATCHER_COMMANDS))
    parser.add_argument("--colmap_executable", default="", type=str)
    parser.add_argument("--resize", action="store_true")
    parser.add_argument("--magick_executable", default="", type=str)
    parser.add_argument("--sift_max_image_size", type=int, default=None)
    parser.add_argument("--sift_max_num_features", type=int, default=None)
    parser.add_argument("--mapper_multiple_models", type=int, default=None)
    parser.add_argument("--mapper_ba_global_function_tolerance", type=float, default=None)
    return parser


def _append_colmap_option(parts: list[str], flag: str, value) -> None:
    if value is None:
        return
    parts.extend([flag, str(value)])


def _run_command(command: str, step_name: str) -> None:
    exit_code = os.system(command)
    if exit_code != 0:
        logging.error("%s failed with code %s. Exiting.", step_name, exit_code)
        raise SystemExit(exit_code)


def registered_image_count(model_dir: str) -> int:
    path = os.path.join(model_dir, "images.bin")
    if not os.path.isfile(path):
        return 0
    with open(path, "rb") as handle:
        header = handle.read(8)
    if len(header) < 8:
        return 0
    return struct.unpack("<Q", header)[0]


def promote_largest_sparse_model(sparse_dir: str) -> str:
    models: list[tuple[int, str, str]] = []
    for name in os.listdir(sparse_dir):
        path = os.path.join(sparse_dir, name)
        if os.path.isdir(path):
            models.append((registered_image_count(path), name, path))
    if not models:
        raise FileNotFoundError(f"COLMAP 未生成稀疏重建: {sparse_dir}")
    models.sort(key=lambda item: (-item[0], item[1] != "0"))
    best_count, best_name, best_path = models[0]
    if best_count <= 0:
        raise FileNotFoundError(f"COLMAP 稀疏重建没有配准图像: {sparse_dir}")
    zero_path = os.path.join(sparse_dir, "0")
    if best_name == "0":
        return zero_path
    if os.path.exists(zero_path):
        swap_path = os.path.join(sparse_dir, "_swap")
        os.rename(zero_path, swap_path)
        os.rename(best_path, zero_path)
        os.rename(swap_path, best_path)
    else:
        os.rename(best_path, zero_path)
    return zero_path


def _feature_extractor_command(args: Namespace, colmap_command: str, use_gpu: int) -> str:
    parts = [
        colmap_command,
        "feature_extractor",
        "--database_path",
        args.source_path + "/distorted/database.db",
        "--image_path",
        args.source_path + "/input",
        "--ImageReader.single_camera",
        "1",
        "--ImageReader.camera_model",
        args.camera,
        "--FeatureExtraction.use_gpu",
        str(use_gpu),
    ]
    _append_colmap_option(parts, "--FeatureExtraction.max_image_size", args.sift_max_image_size)
    _append_colmap_option(parts, "--SiftExtraction.max_num_features", args.sift_max_num_features)
    return " ".join(parts)


def _matcher_command(args: Namespace, colmap_command: str, use_gpu: int) -> str:
    matcher = MATCHER_COMMANDS[args.matcher]
    parts = [
        colmap_command,
        matcher,
        "--database_path",
        args.source_path + "/distorted/database.db",
        "--FeatureMatching.use_gpu",
        str(use_gpu),
    ]
    return " ".join(parts)


def _mapper_command(args: Namespace, colmap_command: str) -> str:
    parts = [
        colmap_command,
        "mapper",
        "--database_path",
        args.source_path + "/distorted/database.db",
        "--image_path",
        args.source_path + "/input",
        "--output_path",
        args.source_path + "/distorted/sparse",
    ]
    _append_colmap_option(parts, "--Mapper.multiple_models", args.mapper_multiple_models)
    _append_colmap_option(
        parts,
        "--Mapper.ba_global_function_tolerance",
        args.mapper_ba_global_function_tolerance,
    )
    return " ".join(parts)


def run(args: Namespace) -> None:
    colmap_command = '"{}"'.format(args.colmap_executable) if len(args.colmap_executable) > 0 else "colmap"
    magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
    use_gpu = 1 if not args.no_gpu else 0

    if not args.skip_matching:
        os.makedirs(args.source_path + "/distorted/sparse", exist_ok=True)
        _run_command(
            _feature_extractor_command(args, colmap_command, use_gpu),
            "Feature extraction",
        )
        _run_command(
            _matcher_command(args, colmap_command, use_gpu),
            f"Feature matching ({args.matcher})",
        )
        _run_command(_mapper_command(args, colmap_command), "Mapper")

    promote_largest_sparse_model(args.source_path + "/distorted/sparse")
    img_undist_cmd = " ".join(
        [
            colmap_command,
            "image_undistorter",
            "--image_path",
            args.source_path + "/input",
            "--input_path",
            args.source_path + "/distorted/sparse/0",
            "--output_path",
            args.source_path,
            "--output_type",
            "COLMAP",
        ]
    )
    _run_command(img_undist_cmd, "Image undistortion")

    files = os.listdir(args.source_path + "/sparse")
    os.makedirs(args.source_path + "/sparse/0", exist_ok=True)
    for file in files:
        if file == "0":
            continue
        source_file = os.path.join(args.source_path, "sparse", file)
        destination_file = os.path.join(args.source_path, "sparse", "0", file)
        shutil.move(source_file, destination_file)

    if args.resize:
        print("Copying and resizing...")
        os.makedirs(args.source_path + "/images_2", exist_ok=True)
        os.makedirs(args.source_path + "/images_4", exist_ok=True)
        os.makedirs(args.source_path + "/images_8", exist_ok=True)
        files = os.listdir(args.source_path + "/images")
        for file in files:
            source_file = os.path.join(args.source_path, "images", file)
            destination_file = os.path.join(args.source_path, "images_2", file)
            shutil.copy2(source_file, destination_file)
            _run_command(magick_command + " mogrify -resize 50% " + destination_file, "50% resize")
            destination_file = os.path.join(args.source_path, "images_4", file)
            shutil.copy2(source_file, destination_file)
            _run_command(magick_command + " mogrify -resize 25% " + destination_file, "25% resize")
            destination_file = os.path.join(args.source_path, "images_8", file)
            shutil.copy2(source_file, destination_file)
            _run_command(magick_command + " mogrify -resize 12.5% " + destination_file, "12.5% resize")

    print("Done.")


if __name__ == "__main__":
    run(_parser().parse_args())
