# syntax=docker/dockerfile:1
#
# 不要加 --no-cache。apt / pip 层会复用，只有 gs_to_pc、scripts 变了才重建 runtime。
#
# 常规构建（首次或改依赖）：
#   docker compose --profile tools build 3dgs-to-pc-worker
#
# 只覆盖业务 Python（本地已有 3dgs-to-pc:latest）：
#   docker compose --profile tools build --target code 3dgs-to-pc-worker
#
# 直接 docker build：
#   docker build -t 3dgs-to-pc:latest --target runtime .
#   docker build -t 3dgs-to-pc:latest --target code --build-arg CODE_BASE=3dgs-to-pc:latest .

ARG PYTORCH_IMAGE=pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime
ARG CODE_BASE=3dgs-to-pc:latest

FROM ${PYTORCH_IMAGE} AS deps

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/conda/bin:$PATH

# --- 层 1：系统库（仅本段变时重做）---
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --- 层 2：Python 依赖（仅本段变时重做）---
RUN pip install --no-cache-dir \
    plyfile \
    open3d \
    numpy \
    tqdm

WORKDIR /workspace/3dgsToPc

# --- 只刷代码：以已有镜像为底，覆盖 gs_to_pc / scripts ---
FROM ${CODE_BASE} AS code
WORKDIR /workspace/3dgsToPc
COPY gs_to_pc ./gs_to_pc
COPY scripts ./scripts

# --- 层 3：完整镜像（改业务 Python 时，只要 deps 缓存还在就只重做本层）---
FROM deps AS runtime
COPY gs_to_pc ./gs_to_pc
COPY scripts ./scripts
