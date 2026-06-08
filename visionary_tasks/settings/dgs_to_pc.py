from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCRIPT = "scripts/ply_to_mesh.py"


@dataclass
class DgsToPcExtractionConfig:
    iteration: int = 30000
    num_points: int = 5_000_000
    mahalanobis_distance_std: float = 2.0
    min_opacity: float = 0.05
    cull_gaussian_sizes: float = 0.0
    max_sh_degree: int = 3
    exact_num_points: bool = False
    clean_pointcloud: bool = True
    poisson_depth: int = 10
    laplacian_iterations: int = 10


@dataclass
class DgsToPcOutputsConfig:
    mesh_ply_names: list[str] = field(default_factory=lambda: ["mesh_poisson.ply"])


@dataclass
class DgsToPcJobConfig:
    worker_image: str
    extraction: DgsToPcExtractionConfig
    outputs: DgsToPcOutputsConfig

    @classmethod
    def from_merged_dict(cls, payload: dict[str, Any]) -> DgsToPcJobConfig:
        outputs_payload = dict(payload.get("outputs") or {})
        return cls(
            worker_image=str(payload.get("worker_image", "3dgs-to-pc:latest")),
            extraction=DgsToPcExtractionConfig(**dict(payload.get("extraction") or {})),
            outputs=DgsToPcOutputsConfig(
                mesh_ply_names=list(outputs_payload.get("mesh_ply_names") or ["mesh_poisson.ply"]),
            ),
        )

    def sync_iteration(self, output_iteration: int) -> DgsToPcJobConfig:
        self.extraction.iteration = output_iteration
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_image": self.worker_image,
            "extraction": asdict(self.extraction),
            "outputs": asdict(self.outputs),
        }

    def to_container_command(self, output_relative: str) -> list[str]:
        ext = self.extraction
        mesh_name = self.outputs.mesh_ply_names[0]
        input_ply = (
            f"/job/{output_relative}/point_cloud/iteration_{ext.iteration}/point_cloud.ply"
        )
        mesh_path = f"/job/{output_relative}/{mesh_name}"
        command = [
            "python",
            SCRIPT,
            "--input_path",
            input_ply,
            "--mesh_output_path",
            mesh_path,
            "--num_points",
            str(ext.num_points),
            "--mahalanobis_distance_std",
            str(ext.mahalanobis_distance_std),
            "--min_opacity",
            str(ext.min_opacity),
            "--cull_gaussian_sizes",
            str(ext.cull_gaussian_sizes),
            "--max_sh_degree",
            str(ext.max_sh_degree),
            "--poisson_depth",
            str(ext.poisson_depth),
            "--laplacian_iterations",
            str(ext.laplacian_iterations),
            "--quiet",
        ]
        if ext.exact_num_points:
            command.append("--exact_num_points")
        if ext.clean_pointcloud:
            command.append("--clean_pointcloud")
        else:
            command.append("--no_clean_pointcloud")
        return command
