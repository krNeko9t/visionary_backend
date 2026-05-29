import json
from typing import Any

from .paths import JobPaths

COLMAP_OUTPUT_NAMES = (
    "sparse",
    "images",
    "distorted",
    "stereo",
    "run-colmap-geometric.sh",
    "run-colmap-photometric.sh",
)


def persist_stage_artifact(
    paths: JobPaths,
    stage_name: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    output_file = paths.stage_artifact_file(stage_name)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = {key: str(value) for key, value in payload.items()}
    result["result"] = str(output_file.relative_to(paths.root))
    return result
