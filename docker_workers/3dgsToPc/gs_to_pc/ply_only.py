"""PLY-only 3DGS → dense point cloud → Poisson mesh (no cameras)."""

from __future__ import annotations

import gc
from math import floor
from typing import NamedTuple

import numpy as np
import torch
from torch.distributions.multivariate_normal import MultivariateNormal
from tqdm import tqdm

from .gauss_dataloader import load_gaussians
from .gauss_handler import Gaussians
from .mesh_handler import clean_point_cloud, generate_mesh


class PointCloudData(NamedTuple):
    points: torch.Tensor
    colours: torch.Tensor
    normals: torch.Tensor | None


class PlyOnlySettings(NamedTuple):
    num_points: int
    mahalanobis_distance_std: float
    min_opacity: float
    bounding_box_min: list[float] | None
    bounding_box_max: list[float] | None
    cull_large_percentage: float
    max_sh_degree: int
    exact_num_points: bool
    clean_pointcloud: bool
    poisson_depth: int
    laplacian_iterations: int
    quiet: bool
    device: str


def distribute_points(gaussian_sizes: torch.Tensor, num_points: int) -> torch.Tensor:
    total_sum = torch.sum(gaussian_sizes)
    points_ratio = num_points / total_sum
    points_per_gaussian = torch.round(gaussian_sizes * points_ratio)
    zero_indices = (points_per_gaussian == 0).nonzero()
    zero_indices = zero_indices[
        : int(
            min(
                (num_points - points_per_gaussian.sum()).item(),
                points_per_gaussian[points_per_gaussian == 0].shape[0],
            )
        )
    ]
    points_per_gaussian[zero_indices] = 1
    return points_per_gaussian


def mahalanobis(means, samples, covs):
    delta = means - samples
    delta = torch.unsqueeze(delta, 2)
    conv_inv = torch.inverse(covs)
    mm_cov_delta = torch.bmm(conv_inv, delta)
    m = torch.bmm(torch.transpose(delta, 1, 2), mm_cov_delta)
    return torch.sqrt(m).squeeze(1).squeeze(1)


def calculate_bin_sizes(points_per_gaussian: torch.Tensor) -> tuple[int, int]:
    distribution = torch.bincount(points_per_gaussian)
    distribution = distribution[distribution.nonzero()].squeeze(1)
    gradients = np.absolute(np.gradient(np.gradient(distribution.cpu().detach().numpy())))
    bin_size = max(len(distribution) // 100, 1)
    length = len(gradients) - len(gradients) % bin_size
    gradients = gradients[:length]
    reshaped_gradients = gradients.reshape(-1, bin_size)
    summed_gradients = reshaped_gradients.sum(axis=1)
    cut_off = np.max(summed_gradients) // 50
    peak = np.argmax(summed_gradients)
    binned_sums = np.nonzero(summed_gradients[peak:] < cut_off)[0]
    start_bin = 1
    if binned_sums.shape[0] != 0:
        start_bin = np.nonzero(summed_gradients[peak:] < cut_off)[0][0]
    return start_bin, bin_size


def sample_from_multivariate_normal(means, covariances, num_points_to_sample, max_num_gen_attempts=3, epsilon=1e-6):
    for _ in range(max_num_gen_attempts):
        try:
            return MultivariateNormal(means, covariances).sample((num_points_to_sample,))
        except Exception:
            covariances += epsilon * torch.eye(3, device=covariances.get_device())
    return None


def create_new_gaussian_points(
    num_points_to_sample,
    means,
    covariances,
    colours,
    mahalanobis_distance_std=2,
    num_attempts=5,
    normals=None,
    device="cuda:0",
):
    total_required_points = num_points_to_sample * means.shape[0]
    added_points = torch.zeros(means.shape[0], device=device)
    max_count = torch.full((means.shape[0],), num_points_to_sample, device=device)
    new_points = torch.tensor([], device=device)
    new_colours = torch.tensor([], device=device).type(torch.double)
    new_normals = torch.tensor([], device=device).type(torch.double) if normals is not None else None

    attempt = 0
    while new_points.shape[0] < total_required_points and attempt < num_attempts:
        gaussians_to_add = added_points != num_points_to_sample
        new_means_for_point = means[gaussians_to_add]
        new_covariances_for_point = covariances[gaussians_to_add]
        new_colours_for_point = colours[gaussians_to_add]
        new_normals_for_point = normals[gaussians_to_add] if normals is not None else None
        gaussians_to_add_idxs = gaussians_to_add.nonzero().squeeze(1)

        original_sampled_points = sample_from_multivariate_normal(
            new_means_for_point, new_covariances_for_point, num_points_to_sample
        )
        if original_sampled_points is None:
            attempt += 1
            continue

        sampled_points = original_sampled_points.transpose(0, 1).contiguous().view(
            -1, original_sampled_points.size(2)
        )
        repeated_means = torch.repeat_interleave(new_means_for_point, num_points_to_sample, dim=0)
        repeated_covariances = torch.repeat_interleave(new_covariances_for_point, num_points_to_sample, dim=0)
        mahalanobis_distances = mahalanobis(repeated_means, sampled_points, repeated_covariances)
        filtered_samples_idxs = mahalanobis_distances <= mahalanobis_distance_std
        filtered_samples = sampled_points[filtered_samples_idxs]

        grouped_idxs = torch.arange(sampled_points.shape[0], device=device)[filtered_samples_idxs].type(torch.float)
        grouped_idxs = torch.floor(torch.div(grouped_idxs, num_points_to_sample))
        counted_idxs, counts = torch.unique(grouped_idxs, return_counts=True)

        all_idxs = torch.arange(new_means_for_point.shape[0], device=device)
        zeroed_indxs = all_idxs[~torch.isin(all_idxs, counted_idxs.type(torch.int))]
        for element in zeroed_indxs:
            counts = torch.cat((counts[:element], torch.tensor([0], device=device), counts[element:]))

        counts = counts[: gaussians_to_add_idxs.shape[0]]
        diffs = torch.min(max_count[gaussians_to_add_idxs] - added_points[gaussians_to_add_idxs], counts).type(
            torch.int
        )
        total_current_points = int(diffs.sum().item())

        indices = torch.arange(len(diffs), device=device) * num_points_to_sample
        expanded_indices = indices.unsqueeze(1) + torch.arange(num_points_to_sample, device=device)
        expanded_indices = expanded_indices.flatten()
        mask = (torch.arange(num_points_to_sample, device=device).unsqueeze(0) < diffs.unsqueeze(1)).flatten()
        filtered_indices = expanded_indices[mask]

        current_points = torch.empty((total_current_points, sampled_points.size(1)), dtype=sampled_points.dtype, device=device)
        current_colours = torch.empty(
            (total_current_points, new_colours_for_point.size(1)), dtype=new_colours_for_point.dtype, device=device
        )
        current_points[:] = sampled_points[filtered_indices]
        current_colours[:] = new_colours_for_point.repeat_interleave(diffs, dim=0)

        added_points[gaussians_to_add_idxs] += counts
        added_points = torch.where(added_points > num_points_to_sample, num_points_to_sample, added_points).type(
            torch.int
        )

        new_points = torch.cat((new_points, current_points), 0)
        new_colours = torch.cat((new_colours, current_colours), 0)

        if normals is not None:
            current_normals = torch.empty(
                (total_current_points, new_normals_for_point.size(1)), dtype=new_normals_for_point.dtype, device=device
            )
            current_normals[:] = new_normals_for_point.repeat_interleave(diffs, dim=0)
            new_normals = torch.cat((new_normals, current_normals), 0)

        attempt += 1

    return new_points, new_colours, new_normals


def generate_pointcloud(
    gaussians: Gaussians,
    num_points: int,
    *,
    mahalanobis_distance_std=2.0,
    exact_num_points=False,
    calculate_normals=True,
    num_sample_attempts=5,
    device="cuda:0",
    quiet=False,
):
    gaussian_sizes = gaussians.get_gaussian_magnitudes()
    points_per_gaussian = distribute_points(gaussian_sizes, num_points).type(torch.int)
    point_distribution = torch.unique(points_per_gaussian)

    if not exact_num_points:
        start_bin, bin_size = calculate_bin_sizes(points_per_gaussian)
        point_distribution = torch.cat(
            (
                point_distribution[:start_bin],
                torch.mul(torch.unique(torch.ceil(point_distribution[start_bin:] / bin_size)), bin_size),
            ),
            0,
        )

    total_points = torch.tensor([], device=device)
    total_colours = torch.tensor([], device=device).type(torch.double)
    total_normals = torch.tensor([], device=device).type(torch.double) if calculate_normals else None

    for i in tqdm(range(point_distribution.shape[0]), position=0, leave=True, disable=quiet):
        start_range = point_distribution[i]
        end_range = point_distribution[i + 1] if i != point_distribution.shape[0] - 1 else start_range + 1
        gaussian_indices = torch.where((points_per_gaussian >= start_range) & (points_per_gaussian < end_range))[0]
        num_points_for_gaussian = floor(start_range + (end_range - start_range) / 2)

        if num_points_for_gaussian <= 0 or gaussian_indices.shape[0] < 1:
            continue

        covariances_for_point = gaussians.covariances[gaussian_indices]
        mean_for_point = gaussians.xyz[gaussian_indices]
        centre_colours = gaussians.colours[gaussian_indices]
        normals_for_point = gaussians.normals[gaussian_indices] if calculate_normals else None

        total_points = torch.cat((total_points, mean_for_point), 0)
        total_colours = torch.cat((total_colours, centre_colours), 0)
        if calculate_normals:
            total_normals = torch.cat((total_normals, normals_for_point), 0)

        if num_points_for_gaussian <= 1:
            continue

        new_points, new_colours, new_normals = create_new_gaussian_points(
            num_points_for_gaussian - 1,
            mean_for_point,
            covariances_for_point,
            centre_colours,
            mahalanobis_distance_std=mahalanobis_distance_std,
            num_attempts=num_sample_attempts,
            normals=normals_for_point,
            device=device,
        )
        total_points = torch.cat((total_points, new_points), 0)
        total_colours = torch.cat((total_colours, new_colours), 0)
        if calculate_normals:
            total_normals = torch.cat((total_normals, new_normals), 0)

    return total_points, total_colours, total_normals


def convert_ply_to_pointcloud(input_path: str, settings: PlyOnlySettings) -> PointCloudData:
    if not settings.quiet:
        print("Loading Gaussians from File")
        print()

    xyz, scales, rots, colours, opacities, shs = load_gaussians(
        input_path, max_sh_degree=settings.max_sh_degree
    )
    gaussians = Gaussians(xyz, scales, rots, colours, opacities, shs=shs)
    gaussians.calculate_normals()

    gaussians.colours *= 255
    gaussians.apply_min_opacity(settings.min_opacity)
    gaussians.apply_bounding_box(settings.bounding_box_min, settings.bounding_box_max)
    gaussians.cull_large_gaussians(settings.cull_large_percentage)
    gaussians.filter_gaussians()

    if gaussians.xyz.shape[0] < 1:
        raise RuntimeError("No Gaussians remain after filtering; cannot build point cloud")

    if not settings.quiet:
        print("Ensuring Gaussians are Positive Semidefinite")
        print()

    gaussians.validate_covariances()

    num_sample_attempts = 100 if settings.exact_num_points else 5
    if not settings.quiet:
        print("Starting Point Cloud Generation")
        print()

    points, colours, normals = generate_pointcloud(
        gaussians,
        settings.num_points,
        mahalanobis_distance_std=settings.mahalanobis_distance_std,
        exact_num_points=settings.exact_num_points,
        calculate_normals=True,
        num_sample_attempts=num_sample_attempts,
        device=settings.device,
        quiet=settings.quiet,
    )

    torch.cuda.empty_cache()
    gc.collect()

    return PointCloudData(points=points, colours=colours, normals=normals)


def run_ply_to_mesh(input_path: str, mesh_output_path: str, settings: PlyOnlySettings) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for 3dgs-to-pc ply-only mesh extraction")

    point_cloud = convert_ply_to_pointcloud(input_path, settings)

    if settings.clean_pointcloud:
        if not settings.quiet:
            print("Cleaning Point Cloud")
            print()
        cleaned_points, cleaned_colours, cleaned_normals = clean_point_cloud(
            point_cloud.points,
            point_cloud.colours,
            point_cloud.normals,
            device=settings.device,
        )
        point_cloud = PointCloudData(
            points=cleaned_points,
            colours=cleaned_colours,
            normals=cleaned_normals,
        )

    if not settings.quiet:
        print("Generating Mesh")
        print()

    generate_mesh(
        point_cloud.points,
        point_cloud.colours,
        point_cloud.normals,
        mesh_output_path,
        depth=settings.poisson_depth,
        laplacian_iters=settings.laplacian_iterations,
    )

    if not settings.quiet:
        print(f"Mesh saved to: {mesh_output_path}")
