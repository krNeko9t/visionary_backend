FROM colmap/colmap:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-minimal \
    python-is-python3 \
    ca-certificates \
&& rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
# 业务脚本（改 convert.py 只重建本层）
COPY convert.py /workspace/convert.py

ENTRYPOINT ["python3", "/workspace/convert.py"]
