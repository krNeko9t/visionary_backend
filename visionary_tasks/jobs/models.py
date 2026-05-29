from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .stages import StageRecord


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    created_at: str
    updated_at: str
    enabled: list[str] = field(default_factory=list)
    stages: list[StageRecord] = field(default_factory=list)

    @classmethod
    def queued(cls, job_id: str, enabled_stages: list[str]) -> "JobRecord":
        timestamp = now_iso()
        return cls(
            job_id=job_id,
            created_at=timestamp,
            updated_at=timestamp,
            enabled=list(enabled_stages),
            stages=[StageRecord.pending(name) for name in enabled_stages],
        )

    def stage_artifact(self, stage_name: str) -> dict[str, Any] | None:
        for stage in self.stages:
            if stage.name == stage_name:
                return stage.artifact
        return None

    def artifacts_map(self) -> dict[str, dict[str, Any] | None]:
        return {stage.name: stage.artifact for stage in self.stages}

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "enabled": self.enabled,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        enabled = list(data.get("enabled") or [])
        raw_stages = data.get("stages") or []
        stages = [StageRecord.from_dict(item) for item in raw_stages if isinstance(item, dict)]
        if not stages and enabled:
            stages = [StageRecord.pending(name) for name in enabled]
        if enabled and stages:
            enabled = [name for name in enabled if any(stage.name == name for stage in stages)]
        elif stages:
            enabled = [stage.name for stage in stages]
        return cls(
            job_id=data["job_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            enabled=enabled,
            stages=stages,
        )

    def parse_created_at(self) -> datetime:
        return datetime.fromisoformat(self.created_at)

    def parse_updated_at(self) -> datetime:
        return datetime.fromisoformat(self.updated_at)
