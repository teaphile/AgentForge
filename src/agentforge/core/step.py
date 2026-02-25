"""Workflow step and parallel group definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    """Binds an agent to a task with optional control flow (conditions, branching, retries)."""

    id: str
    agent: str  # agent key name
    task: str  # task template (may contain {{variables}})
    output_format: str = "text"  # "text" | "markdown" | "json"
    timeout: int | None = None
    retry_on_fail: int | None = None
    approval_gate: bool = False
    dry_run: bool | None = None
    condition: str | None = None
    save_as: str | None = None
    on_success: str | None = None
    on_fail: str | None = None
    next: str | None = None  # loop to another step

    @classmethod
    def from_config(cls, step_config: dict) -> "Step":
        return cls(
            id=step_config["id"],
            agent=step_config["agent"],
            task=step_config["task"],
            output_format=step_config.get("output_format", "text"),
            timeout=step_config.get("timeout"),
            retry_on_fail=step_config.get("retry_on_fail"),
            approval_gate=step_config.get("approval_gate", False),
            dry_run=step_config.get("dry_run"),
            condition=step_config.get("condition"),
            save_as=step_config.get("save_as"),
            on_success=step_config.get("on_success"),
            on_fail=step_config.get("on_fail"),
            next=step_config.get("next"),
        )


@dataclass
class ParallelGroup:
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def from_config(cls, parallel_config: list[dict]) -> "ParallelGroup":
        steps = [Step.from_config(s) for s in parallel_config]
        return cls(steps=steps)
