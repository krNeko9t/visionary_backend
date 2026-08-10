FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY visionary_tasks /workspace/visionary_tasks

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        python-multipart \
        pydantic \
        docker \
        pyyaml \
        trimesh

CMD ["uvicorn", "visionary_tasks.main:app", "--host", "0.0.0.0", "--port", "8000"]
