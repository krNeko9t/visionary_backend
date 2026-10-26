FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        python-multipart \
        pydantic \
        docker \
        pyyaml \
        trimesh \
        pillow

COPY pyproject.toml /tmp/visionary-progress/pyproject.toml
COPY visionary_progress/ /tmp/visionary-progress/visionary_progress/
RUN pip install --no-deps /tmp/visionary-progress && rm -rf /tmp/visionary-progress

COPY visionary_tasks /workspace/visionary_tasks

CMD ["uvicorn", "visionary_tasks.main:app", "--host", "0.0.0.0", "--port", "8000"]
