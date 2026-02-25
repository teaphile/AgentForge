"""Tests for Step and ParallelGroup."""

from __future__ import annotations


from agentforge.core.step import Step, ParallelGroup


class TestStep:
    def test_basic_step(self):
        step = Step(id="s1", agent="writer", task="Write a poem")
        assert step.id == "s1"
        assert step.agent == "writer"
        assert step.task == "Write a poem"

    def test_step_defaults(self):
        step = Step(id="s1", agent="a", task="t")
        assert step.timeout is None or step.timeout == 0
        assert step.retry_on_fail is False or step.retry_on_fail is None
        assert step.approval_gate is False or step.approval_gate is None
        assert step.dry_run is False or step.dry_run is None

    def test_step_with_all_fields(self):
        step = Step(
            id="s1",
            agent="a",
            task="t",
            output_format="json",
            timeout=60,
            retry_on_fail=True,
            approval_gate=True,
            dry_run=True,
            condition="len(input) > 0",
            save_as="result",
            on_success="next_step",
            on_fail="error_step",
            next="loop_step",
        )
        assert step.output_format == "json"
        assert step.timeout == 60
        assert step.retry_on_fail is True
        assert step.approval_gate is True
        assert step.save_as == "result"
        assert step.on_success == "next_step"
        assert step.on_fail == "error_step"


class TestParallelGroup:
    def test_parallel_group(self):
        steps = [
            Step(id="s1", agent="a", task="t1"),
            Step(id="s2", agent="b", task="t2"),
        ]
        group = ParallelGroup(steps=steps)
        assert len(group.steps) == 2

    def test_parallel_group_empty(self):
        group = ParallelGroup(steps=[])
        assert len(group.steps) == 0
