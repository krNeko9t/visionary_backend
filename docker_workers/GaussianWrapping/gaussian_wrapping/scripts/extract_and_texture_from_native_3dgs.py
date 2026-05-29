import argparse
import os
import subprocess
import sys

from plyfile import PlyData


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT_SCRIPT = os.path.join(BASE_DIR, "pivot_based_mesh_extraction.py")
TEXTURE_SCRIPT = os.path.join(BASE_DIR, "texture_mesh.py")
DECIMATE_SCRIPT = os.path.join(BASE_DIR, "mesh_decimate.py")


def parse_shared_data_args(raw_args):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-s", "--source_path")
    parser.add_argument("-m", "--model_path")
    parser.add_argument("-r", "--resolution")
    known, _ = parser.parse_known_args(raw_args)
    return known


def check_colmap_layout(source_path):
    if not source_path:
        raise ValueError("Missing -s/--source_path.")
    if not os.path.isdir(source_path):
        raise FileNotFoundError(f"Dataset root does not exist: {source_path}")

    images_dir = os.path.join(source_path, "images")
    sparse_dir = os.path.join(source_path, "sparse")
    sparse0_dir = os.path.join(sparse_dir, "0")

    if not os.path.isdir(images_dir):
        raise FileNotFoundError(
            f"Missing COLMAP images directory: {images_dir}"
        )
    if not os.path.isdir(sparse_dir):
        raise FileNotFoundError(
            f"Missing COLMAP sparse directory: {sparse_dir}"
        )
    if not os.path.isdir(sparse0_dir):
        raise FileNotFoundError(
            f"Missing COLMAP sparse/0 directory: {sparse0_dir}"
        )

    has_bin = all(
        os.path.isfile(os.path.join(sparse0_dir, f))
        for f in ("cameras.bin", "images.bin", "points3D.bin")
    )
    has_txt = all(
        os.path.isfile(os.path.join(sparse0_dir, f))
        for f in ("cameras.txt", "images.txt", "points3D.txt")
    )
    if not (has_bin or has_txt):
        raise FileNotFoundError(
            "COLMAP sparse/0 must contain either "
            "(cameras.bin, images.bin, points3D.bin) "
            "or (cameras.txt, images.txt, points3D.txt)."
        )


def check_native_point_cloud(model_path, iteration):
    if not model_path:
        raise ValueError("Missing -m/--model_path.")
    if not os.path.isdir(model_path):
        raise FileNotFoundError(f"Model root does not exist: {model_path}")

    ply_path = os.path.join(
        model_path, "point_cloud", f"iteration_{iteration}", "point_cloud.ply"
    )
    if not os.path.isfile(ply_path):
        raise FileNotFoundError(
            "Missing point cloud PLY. Expected path:\n"
            f"{ply_path}"
        )

    ply = PlyData.read(ply_path)
    if len(ply.elements) == 0 or ply.elements[0].name != "vertex":
        raise ValueError(f"Invalid PLY: no vertex element in {ply_path}")

    prop_names = {prop.name for prop in ply.elements[0].properties}
    required_exact = {"x", "y", "z", "opacity", "f_dc_0", "f_dc_1", "f_dc_2"}
    missing_exact = sorted(required_exact - prop_names)
    if missing_exact:
        raise ValueError(
            f"point_cloud.ply is missing required fields: {missing_exact}"
        )

    if not any(name.startswith("f_rest_") for name in prop_names):
        raise ValueError("point_cloud.ply has no f_rest_* fields (SH coefficients).")
    if not any(name.startswith("scale_") for name in prop_names):
        raise ValueError("point_cloud.ply has no scale_* fields.")
    if not any(name.startswith("rot_") for name in prop_names):
        raise ValueError("point_cloud.ply has no rot_* fields.")

    return ply_path, any(name.startswith("gaussian_features_") for name in prop_names)


def ensure_cfg_args(model_path, source_path, resolution):
    cfg_path = os.path.join(model_path, "cfg_args")
    if os.path.isfile(cfg_path):
        return cfg_path, False

    # Extraction/texture scripts call get_combined_args(), which expects this file.
    # Create a minimal compatible namespace for native checkpoints.
    cfg_content = (
        "Namespace("
        f"source_path='{source_path}', "
        f"model_path='{model_path}', "
        "images='images', "
        f"resolution={resolution if resolution is not None else -1}, "
        "white_background=False, "
        "data_device='cpu', "
        "eval=False, "
        "llff=8, "
        "kernel_size=0.0, "
        "use_unbounded_opacity=False, "
        "sh_degree=3"
        ")"
    )
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(cfg_content)
    return cfg_path, True


def main():
    parser = argparse.ArgumentParser(
        description="Run GW extraction + texture refinement from an external/native 3DGS checkpoint."
    )
    parser.add_argument("--iteration", type=int, default=30000)
    parser.add_argument("--rasterizer", type=str, default="ours", choices=["ours", "radegs"])
    parser.add_argument(
        "--sdf_mode",
        type=str,
        default="ours",
        choices=["ours", "exact_computation"],
        help="SDF backend for stage 2 extraction.",
    )
    parser.add_argument("--n_pivots", type=int, default=2)
    parser.add_argument("--n_binary_steps", type=int, default=10)
    parser.add_argument("--isosurface_value", type=float, default=0.0)
    parser.add_argument("--dtype", type=str, default="int32", choices=["int32", "int64"])
    parser.add_argument("--use_valid_mask", action="store_true", default=True)
    parser.add_argument("--no_use_valid_mask", action="store_true")
    parser.add_argument("--postprocess", action="store_true", default=True)
    parser.add_argument("--no_postprocess", action="store_true")
    parser.add_argument("--filter_large_edges", action="store_true", default=True)
    parser.add_argument("--no_filter_large_edges", action="store_true")
    parser.add_argument("--mesh", type=str, default=None, help="Skip stage 2 and texture this mesh directly.")
    parser.add_argument("--texture_n_iter", type=int, default=1000)
    parser.add_argument("--texture_lr", type=float, default=0.0025)
    parser.add_argument("--texture_lambda_dssim", type=float, default=0.2)
    parser.add_argument("--texture_sh_degree", type=int, default=0)
    parser.add_argument("--apply_decimation", action="store_true")
    parser.add_argument("--decimate_ratio", type=float, default=0.3)
    args, raw_unknown = parser.parse_known_args(sys.argv[1:])

    shared = parse_shared_data_args(raw_unknown)
    check_colmap_layout(shared.source_path)
    _, has_gaussian_features = check_native_point_cloud(shared.model_path, args.iteration)
    cfg_path, cfg_created = ensure_cfg_args(
        model_path=shared.model_path,
        source_path=shared.source_path,
        resolution=shared.resolution,
    )
    if cfg_created:
        print(f"[WARNING] Missing cfg_args. Created a minimal one at: {cfg_path}")

    shared_args = []
    if shared.source_path:
        shared_args += ["-s", shared.source_path]
    if shared.model_path:
        shared_args += ["-m", shared.model_path]
    if shared.resolution:
        shared_args += ["-r", shared.resolution]

    use_valid_mask = args.use_valid_mask and not args.no_use_valid_mask
    postprocess = args.postprocess and not args.no_postprocess
    filter_large_edges = args.filter_large_edges and not args.no_filter_large_edges

    mesh_path = args.mesh
    if mesh_path is None:
        print("[INFO] Step 1/2: Extracting mesh from native 3DGS output...")
        extract_cmd = [
            sys.executable,
            EXTRACT_SCRIPT,
            "--iteration",
            str(args.iteration),
            "--rasterizer",
            args.rasterizer,
            "--sdf_mode",
            args.sdf_mode,
            "--dtype",
            args.dtype,
            "--n_pivots",
            str(args.n_pivots),
            "--n_binary_steps",
            str(args.n_binary_steps),
            "--isosurface_value",
            str(args.isosurface_value),
            "--data_device",
            "cpu",
        ] + shared_args

        # Native Inria 3DGS checkpoints typically lack gaussian_features_*.
        if not has_gaussian_features:
            extract_cmd.append("--use_smallest_axis_as_normal")

        if use_valid_mask:
            extract_cmd.append("--use_valid_mask")
        if postprocess:
            extract_cmd.append("--postprocess")
        if filter_large_edges:
            extract_cmd.append("--filter_large_edges")

        result = subprocess.run(extract_cmd)
        if result.returncode != 0:
            print("[ERROR] Mesh extraction failed. Aborting texture refinement.")
            sys.exit(result.returncode)

        if args.sdf_mode == "exact_computation":
            transmittance_threshold = 0.5 + args.isosurface_value
            if transmittance_threshold != 0.5:
                iso_suffix = f"_transmittance_threshold_{transmittance_threshold}"
            else:
                iso_suffix = ""
        elif args.isosurface_value != 0:
            iso_suffix = f"_iso_{args.isosurface_value}"
        else:
            iso_suffix = ""

        mesh_name = f"mesh_{args.sdf_mode}_{args.n_pivots}pivots{iso_suffix}.ply"
        mesh_path = os.path.join(shared.model_path, mesh_name)
        if postprocess:
            mesh_path = mesh_path.replace(".ply", "_post.ply")

    if args.apply_decimation:
        print(f"[INFO] Step 1.5/2: Decimating mesh with ratio {args.decimate_ratio}...")
        decimate_cmd = [
            "blender",
            "-b",
            "-P",
            DECIMATE_SCRIPT,
            "--",
            "--in",
            mesh_path,
            "--ratio",
            str(args.decimate_ratio),
        ]
        result = subprocess.run(decimate_cmd)
        if result.returncode != 0:
            print("[ERROR] Mesh decimation failed. Aborting texture refinement.")
            sys.exit(result.returncode)
        mesh_path = mesh_path.replace(".ply", "_decimated_with_blender.ply")

    print("[INFO] Step 2/2: Refining mesh texture...")
    texture_cmd = [
        sys.executable,
        TEXTURE_SCRIPT,
        "--iteration",
        str(args.iteration),
        "--rasterizer",
        args.rasterizer,
        "--mesh",
        mesh_path,
        "--n_iter",
        str(args.texture_n_iter),
        "--lr",
        str(args.texture_lr),
        "--lambda_dssim",
        str(args.texture_lambda_dssim),
        "--sh_degree_for_texturing",
        str(args.texture_sh_degree),
    ] + shared_args

    result = subprocess.run(texture_cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
