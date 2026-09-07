# LangSplatV2 — 基于官方 PyTorch 镜像，使用 pip 安装 Python 依赖（见 requirements-docker.txt）
#
# 构建前请确保 submodules 源码已完整包含在仓库中（docker_workers/LangSplatV2/submodules/）。
#
# 默认：PyTorch 2.4.1 + CUDA 12.4（devel 含 nvcc，便于编译子模块扩展）。
# 可选用 2.2.0 + CUDA 12.1：
#   docker build --build-arg PYTORCH_IMAGE=pytorch/pytorch:2.2.0-cuda12.1-cudnn8-devel .
#
# 分层：改业务 Python 只重建最后一层，不必重编 CUDA 扩展。

ARG PYTORCH_IMAGE=pytorch/pytorch:2.4.1-cuda12.4-cudnn9-devel
FROM ${PYTORCH_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# 按需裁剪算力架构可缩短 diff_gaussian_rasterization / simple_knn 编译时间（默认覆盖常见 GPU）
ARG TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0"
ENV TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    build-essential \
    ninja-build \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# --- 层 1：pip 依赖（仅 requirements-docker.txt 变时重做）---
COPY requirements-docker.txt /workspace/requirements-docker.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /workspace/requirements-docker.txt \
    && pip install --no-cache-dir "open-clip-torch>=2.16.0,<2.23.0" --no-deps

# --- 层 2：编译 CUDA 扩展 / 安装 SAM（仅 submodules/ 变时重做）---
COPY submodules/ /workspace/submodules/

RUN pip install --no-cache-dir --no-build-isolation \
        submodules/simple-knn \
        submodules/efficient-langsplat-rasterization \
    && pip install --no-cache-dir submodules/segment-anything-langsplat

# --- 层 3：业务 Python（改脚本只重做本层）---
COPY train.py preprocess.py export_lsv2_final_product.py convert.py ./
COPY eval_lerf.py eval_mip_nerf360.py eval_3d_ovs.py ./
COPY scene/ scene/
COPY gaussian_renderer/ gaussian_renderer/
COPY utils/ utils/
COPY arguments/ arguments/
COPY eval/ eval/
COPY lpipsPyTorch/ lpipsPyTorch/

# preprocess.py 默认读取 ckpts/sam_vit_h_4b8939.pth，请挂载或复制权重到该路径
ENV PYTHONPATH=/workspace

CMD ["bash"]
