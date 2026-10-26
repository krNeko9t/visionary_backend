from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

StepId = dict[str, str | int]


@dataclass
class CurrentStep:
    """A partial update; None means absent, and identity changes clear details.

    Counts derive a clamped fraction when both are present. An explicit fraction
    must agree with counts in the same record. During replay, a new explicit
    fraction supersedes old, incompatible counts from an earlier record.
    """

    id: StepId
    label: str | None = None
    progress: float | None = None
    completed: float | None = None
    total: float | None = None
    unit: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.id or any(
            not isinstance(key, str) or not isinstance(value, (str, int))
            for key, value in self.id.items()
        ):
            raise ValueError("current_step.id must be a non-empty structured identity")
        for name in ("progress", "completed", "total"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"current_step.{name} must be finite and non-negative")
        if self.total is not None and self.total <= 0:
            raise ValueError("current_step.total must be positive")
        if self.progress is not None and self.progress > 1:
            raise ValueError("current_step.progress must be in [0, 1]")
        if self.completed is not None and self.total is not None:
            fraction = min(1.0, self.completed / self.total)
            if self.progress is not None and not math.isclose(self.progress, fraction):
                raise ValueError("current_step.progress must agree with completed/total")
            self.progress = fraction

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurrentStep:
        return cls(**data)


@dataclass
class StepDefinition:
    """Identity and share; execution order is the containing list's order."""

    id: StepId
    label: str
    weight: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProgressEvent:
    stage_id: str
    event_type: str
    progress: float | None = None  # Legacy stage fraction, never a local fraction.
    iteration: int | None = None
    total_iterations: int | None = None
    message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_step: CurrentStep | None = None

    def __post_init__(self) -> None:
        step = self.current_step
        if step is not None and step.unit == "iteration":
            for field_name, value in (("iteration", step.completed), ("total_iterations", step.total)):
                if value is None:
                    continue
                if int(value) != value:
                    raise ValueError("iteration counts must be integers")
                existing = getattr(self, field_name)
                if existing is not None and existing != value:
                    raise ValueError(f"{field_name} must agree with current_step counts")
                setattr(self, field_name, int(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProgressEvent:
        return cls(
            stage_id=str(data["stage_id"]),
            event_type=str(data["event_type"]),
            progress=data.get("progress"),
            iteration=data.get("iteration"),
            total_iterations=data.get("total_iterations"),
            message=data.get("message"),
            timestamp=str(data.get("timestamp", "")),
            current_step=CurrentStep.from_dict(data["current_step"]) if data.get("current_step") else None,
        )


def make_progress_event(
    stage_id: str,
    *,
    event_type: str = "progress",
    progress: float | None = None,
    iteration: int | None = None,
    total_iterations: int | None = None,
    message: str | None = None,
    current_step: CurrentStep | None = None,
) -> ProgressEvent:
    return ProgressEvent(
        stage_id=stage_id, event_type=event_type, progress=progress,
        iteration=iteration, total_iterations=total_iterations,
        message=message, current_step=current_step,
    )


def append_progress_event(path: Path, event: ProgressEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.to_dict(), ensure_ascii=False, allow_nan=False) + "\n")


def read_progress_events(path: Path) -> list[ProgressEvent]:
    if not path.exists():
        return []
    # Split bytes first: an append may stop inside a UTF-8 character as well as JSON.
    lines = path.read_bytes().split(b"\n")
    events = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if index == len(lines) - 1:
                break  # The writer will finish this record on a subsequent read.
            raise
        events.append(ProgressEvent.from_dict(payload))
    return events


def record_progress(path: Path, stage_id: str, **fields: Any) -> ProgressEvent:
    event = make_progress_event(stage_id, **fields)
    append_progress_event(path, event)
    return event


@dataclass
class ProgressReporter:
    """Worker adapter: binds backend-supplied context, reports only local work."""

    path: Path | None
    stage_id: str
    step_id: StepId
    label: str

    @classmethod
    def from_env(cls) -> ProgressReporter:
        path = os.environ.get("VISIONARY_PROGRESS_FILE")
        return cls(
            Path(path) if path else None,
            os.environ.get("VISIONARY_PROGRESS_STAGE", ""),
            json.loads(os.environ.get("VISIONARY_PROGRESS_STEP", "{}")),
            os.environ.get("VISIONARY_PROGRESS_LABEL", ""),
        )

    def environment(self) -> dict[str, str]:
        return {
            "VISIONARY_PROGRESS_FILE": str(self.path) if self.path else "",
            "VISIONARY_PROGRESS_STAGE": self.stage_id,
            "VISIONARY_PROGRESS_STEP": json.dumps(self.step_id),
            "VISIONARY_PROGRESS_LABEL": self.label,
        }

    def record(
        self, *, event_type: str = "progress", progress: float | None = None,
        completed: float | None = None, total: float | None = None,
        unit: str | None = None, message: str | None = None,
    ) -> None:
        if self.path is None:
            return
        record_progress(
            self.path, self.stage_id, event_type=event_type, message=message,
            current_step=CurrentStep(
                id=self.step_id, label=self.label, progress=progress,
                completed=completed, total=total, unit=unit, message=message,
            ),
        )
