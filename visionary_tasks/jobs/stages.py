from dataclasses import dataclass
from typing import Any, Literal

StageStatus = Literal["pending", "running", "done", "error", "skipped"]


@dataclass
class StageRecord:
    name: str
    status: StageStatus
    started_at: str | None = None
    ended_at: str | None = None
    artifact: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def pending(cls, name: str) -> "StageRecord":
        return cls(name=name, status="pending")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "artifact": self.artifact,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageRecord":
        return cls(
            name=str(data["name"]),
            status=str(data["status"]),  # type: ignore[arg-type]
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            artifact=data.get("artifact"),
            error=data.get("error"),
        )
