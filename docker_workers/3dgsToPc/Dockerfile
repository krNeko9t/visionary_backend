# syntax=docker/dockerfile:1
# Build:
#   DOCKER_BUILDKIT=1 docker build -t 3dgs-to-pc:latest .
# Run:
#   docker run --gpus all --rm -v <job>:/job 3dgs-to-pc:latest \
#     python scripts/ply_to_mesh.py --input_path /job/output/.../point_cloud.ply \
#     --mesh_output_path /job/output/mesh_poisson.ply --quiet

ARG PYTORCH_IMAGE=pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime
FROM ${PYTORCH_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/conda/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    plyfile \
    open3d \
    numpy \
    tqdm

WORKDIR /workspace/3dgsToPc

# 业务 Python（无 CUDA 扩展；改脚本只重建本层）
COPY gs_to_pc ./gs_to_pc
COPY scripts ./scripts
