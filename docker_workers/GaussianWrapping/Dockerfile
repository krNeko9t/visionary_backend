# syntax=docker/dockerfile:1
# Build (from GaussianWrapping directory):
#   DOCKER_BUILDKIT=1 docker build -t gaussian-wrapping .
# Run (GPU):
#   docker run --gpus all -it --rm -v <data>:/data gaussian-wrapping
#
# 开发时只改 Python 可挂载子目录，避免覆盖镜像里已编译的 submodules：
#   -v <repo>/gaussian_wrapping:/workspace/GaussianWrapping/gaussian_wrapping
# 若挂载整个仓库到 /workspace/GaussianWrapping，会盖住镜像内 submodules 的 .so，需本机也编好 submodule。

ARG PYTORCH_IMAGE=pytorch/pytorch:2.4.1-cuda12.4-cudnn9-devel
FROM ${PYTORCH_IMAGE}

# docker build 默认无 GPU，必须显式指定架构，否则 torch/cpp_extension 里 arch_list 为空会报错
ARG TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0"
ARG BLENDER_VERSION=4.0.2
ENV TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST}

ENV DEBIAN_FRONTEND=noninteractive \
    CONDA_PREFIX=/opt/conda \
    PATH=/opt/conda/bin:$PATH \
    FORCE_CUDA=1 \
    CUDA_HOME=/usr/local/cuda \
    CPATH=/usr/local/cuda/include:/opt/conda/include \
    NVDIFFRAST_USE_OPENGL=0

# open3d：运行时需 libX11；nvdiffrast GL 插件：编译/运行需 EGL + GL 开发包
# Blender：mesh_decimate.py（--apply_decimation）无头减面，版本与 milo_addon 一致
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    ninja-build \
    zlib1g-dev \
    wget \
    xz-utils \
    libx11-6 \
    libgl1 \
    libglib2.0-0 \
    libegl1-mesa-dev \
    libgl1-mesa-dev \
    libgles2-mesa-dev \
    libxrender1 \
    libxi6 \
    libxxf86vm1 \
    libxfixes3 \
    libxkbcommon0 \
    libglu1-mesa \
    libsm6 \
    libice6 \
    libfontconfig1 \
    libfreetype6 \
    libjpeg-turbo8 \
    libpng16-16 \
    && wget -q "https://download.blender.org/release/Blender4.0/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    && tar -xf "blender-${BLENDER_VERSION}-linux-x64.tar.xz" -C /opt \
    && ln -sf "/opt/blender-${BLENDER_VERSION}-linux-x64/blender" /usr/local/bin/blender \
    && rm "blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    && blender --version \
    && rm -rf /var/lib/apt/lists/*

# tetra_triangulation 的 CMake 在 CONDA_PREFIX 下查找 cnpy/CGAL。
RUN conda install -y pip=22.3.1 && \
    conda install -y -c conda-forge \
    cmake \
    gmp \
    cgal \
    && conda clean -afy && \
    git clone --depth 1 https://github.com/rogersce/cnpy.git /tmp/cnpy && \
    cmake -S /tmp/cnpy -B /tmp/cnpy/build \
        -DCMAKE_INSTALL_PREFIX=/opt/conda \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DENABLE_STATIC=OFF && \
    cmake --build /tmp/cnpy/build -j"$(nproc)" && \
    cmake --install /tmp/cnpy/build && \
    rm -rf /tmp/cnpy

WORKDIR /workspace/GaussianWrapping

ARG PYG_WHL_URL=https://data.pyg.org/whl/torch-2.4.0+cu124.html
ENV PYG_WHL_URL=${PYG_WHL_URL}

# --- 层 1：pip 依赖（仅 requirements-docker.txt 变时重做）---
COPY requirements-docker.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-docker.txt

# --- 层 2：编译 submodules（仅 submodules/ 变时重做）---
COPY submodules/ submodules/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-build-isolation submodules/diff-gaussian-rasterization_ms && \
    pip install --no-build-isolation submodules/diff-gaussian-rasterization && \
    pip install --no-build-isolation submodules/diff-gaussian-rasterization_ours && \
    pip install --no-build-isolation submodules/diff-gaussian-rasterization_sof && \
    pip install --no-build-isolation submodules/simple-knn && \
    pip install --no-build-isolation submodules/fused-ssim

RUN --mount=type=cache,target=/root/.cache/pip \
    cd submodules/tetra_triangulation && \
    cmake . -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_PREFIX_PATH="$(python -c 'import torch; print(torch.utils.cmake_prefix_path)')" && \
    make -j"$(nproc)" && \
    pip install --no-build-isolation -e . && \
    cd /workspace/GaussianWrapping

# nvdiffrast 插件在首次使用时 JIT 编译（需 docker run --gpus all；build 无 GPU 且会清空 TORCH_CUDA_ARCH_LIST，不能在此预编译）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-build-isolation -e submodules/nvdiffrast && \
    pip install --no-build-isolation \
        submodules/Geometry-Grounded-Gaussian-Splatting/submodules/warp-patch-ncc

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch_geometric && \
    pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv \
        -f "${PYG_WHL_URL}"

# --- 层 3：业务代码（改 gaussian_wrapping/ 只重做本层，秒级）---
COPY gaussian_wrapping/ gaussian_wrapping/

WORKDIR /workspace/GaussianWrapping
CMD ["/bin/bash"]
