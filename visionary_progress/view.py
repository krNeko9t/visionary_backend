from __future__ import annotations

import re
import math
from dataclasses import replace

from .events import CurrentStep, ProgressEvent, StepDefinition, StepId


def _key(identity: StepId) -> tuple[tuple[str, str | int], ...]:
    return tuple(sorted(identity.items()))


def _legacy_step(event: ProgressEvent) -> CurrentStep | None:
    # Compatibility for training events written before structured identities existed.
    if event.stage_id == "langsplat" and event.iteration is not None:
        match = re.search(r"\blevel=(-?\d+)\b", event.message or "")
        if match and event.total_iterations and event.total_iterations > 0:
            level = int(match[1])
            return CurrentStep(
                id={"name": "train", "level": level}, label=f"训练 level={level}",
                completed=event.iteration, total=event.total_iterations,
                unit="iteration", message=event.message,
            )
    return None


class StageProgress:
    """Replay once, using the same projection for event history and job views."""

    def __init__(self, steps: list[StepDefinition]) -> None:
        self.steps = steps
        self.progress: float | None = None
        self.current_step: CurrentStep | None = None
        self._fractions: dict[tuple[tuple[str, str | int], ...], float] = {}

    def consume(self, event: ProgressEvent) -> ProgressEvent:
        if event.progress is not None:
            self.progress = max(0.0, min(1.0, event.progress))
            # Old stage milestones also account for earlier work in the declaration.
            remaining = self.progress
            for definition in self.steps:
                if definition.weight > 0:
                    self._fractions[_key(definition.id)] = min(1.0, max(0.0, remaining / definition.weight))
                remaining -= definition.weight

        update = event.current_step or _legacy_step(event)
        if update is not None:
            same_work = self.current_step is not None and self.current_step.id == update.id
            details = self.current_step.to_dict() if same_work and self.current_step else {}
            details.update({key: value for key, value in update.to_dict().items() if value is not None})
            if (update.completed is not None or update.total is not None) and details.get("completed") is not None and details.get("total"):
                details["progress"] = update.progress
            elif update.progress is not None and details.get("completed") is not None and details.get("total"):
                if not math.isclose(update.progress, min(1.0, details["completed"] / details["total"])):
                    details["completed"] = None
                    details["total"] = None
                    details["unit"] = None
            if event.message is not None and update.message is None:
                details["message"] = event.message
            current_definition = next((step for step in self.steps if step.id == update.id), None)
            details.setdefault("label", current_definition.label if current_definition else str(update.id))
            self.current_step = CurrentStep.from_dict(details)
            if self.current_step.progress is not None:
                self._fractions[_key(update.id)] = self.current_step.progress
                fraction = sum(step.weight * self._fractions.get(_key(step.id), 0.0) for step in self.steps)
                self.progress = max(self.progress or 0.0, min(1.0, fraction))
        elif event.message is not None and self.current_step is not None:
            self.current_step = replace(self.current_step, message=event.message)

        projected_step = self.current_step
        if update is None and projected_step is not None and projected_step.unit == "iteration":
            # An unscoped legacy milestone may count the whole stage rather than
            # the last internal work. Preserve its aliases without attributing
            # those counts to a work identity the producer never supplied.
            counts = ((event.iteration, projected_step.completed),
                      (event.total_iterations, projected_step.total))
            if any(legacy is not None and local is not None and legacy != local for legacy, local in counts):
                projected_step = None
        return replace(event, progress=self.progress, current_step=projected_step)
