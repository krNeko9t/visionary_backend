FROM zachduan/3d-vision:cu118-torch21-3dgs

ENV MAX_JOBS=8
ENV PATH=/opt/miniconda3/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# docker build 时容器里通常看不到 GPU，PyTorch 无法自动推断 CUDA 架构，会在
# _get_cuda_arch_flags 里得到空列表并触发 IndexError。此处显式指定要打进
# wheel 的架构；与本机显卡不一致时可 build-arg 覆盖，例如：
# docker compose build --build-arg TORCH_CUDA_ARCH_LIST=8.6 task-server
# 7.0;7.5;8.0;8.6;8.9
ARG TORCH_CUDA_ARCH_LIST="8.9"
ENV TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST}

WORKDIR /workspace

COPY gaussian-splatting /workspace/gaussian-splatting
COPY visionary_tasks /workspace/visionary_tasks

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        python-multipart \
        pydantic \
        docker \
        pyyaml \
        ninja \
        trimesh \
    && pip install --no-cache-dir /workspace/gaussian-splatting/submodules/diff-gaussian-rasterization --no-build-isolation \
    && pip install --no-cache-dir /workspace/gaussian-splatting/submodules/simple-knn --no-build-isolation

CMD ["uvicorn", "visionary_tasks.main:app", "--host", "0.0.0.0", "--port", "8000"]
