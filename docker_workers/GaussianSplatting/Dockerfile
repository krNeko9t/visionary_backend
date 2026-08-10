FROM zachduan/3d-vision:cu118-torch21-3dgs

ENV PATH=/opt/miniconda3/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# docker build 时容器里通常看不到 GPU，PyTorch 无法自动推断 CUDA 架构。
# 与本机显卡不一致时可通过 --build-arg TORCH_CUDA_ARCH_LIST=... 覆盖。
ARG TORCH_CUDA_ARCH_LIST="8.9"
ENV TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST}

WORKDIR /workspace/gaussian-splatting

COPY source /workspace/gaussian-splatting

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ninja \
    && pip install --no-cache-dir \
        /workspace/gaussian-splatting/submodules/diff-gaussian-rasterization \
        --no-build-isolation \
    && pip install --no-cache-dir \
        /workspace/gaussian-splatting/submodules/simple-knn \
        --no-build-isolation
