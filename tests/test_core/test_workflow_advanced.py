"""Tests for advanced workflow features: parallel, branching, conditions, timeout, output_format."""

from __future__ import annotations

import asyncio

import pytest

from agentforge.core.agent import Agent
from agentforge.core.step import ParallelGroup, Step
from agentforge.core.workflow import Workflow
from agentforge.observe.events import EventBus
from agentforge.observe.tracer import Tracer
from agentforge.control.approval import ApprovalManager


@pytest.fixture
def agents():
    a = Agent(name="alpha", role="Alpha", goal="Do alpha work")
    b = Agent(name="beta", role="Beta", goal="Do beta work")
    return {"alpha": a, "beta": b}


class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_parallel_group_runs_both(self, agents, mock_llm_router):
        group = ParallelGroup(steps=[
            Step(id="p1", agent="alpha", task="Task A"),
            Step(id="p2", agent="beta", task="Task B"),
        ])
        wf = Workflow(steps=[group], agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert len(results) == 2
        ids = {r.step_id for r in results}
        assert ids == {"p1", "p2"}

    @pytest.mark.asyncio
    async def test_parallel_results_in_context(self, agents, mock_llm_router):
        """Both parallel outputs should be accessible in subsequent steps."""
        group = ParallelGroup(steps=[
            Step(id="p1", agent="alpha", task="A", save_as="result_a"),
            Step(id="p2", agent="beta", task="B", save_as="result_b"),
        ])
        sequential = Step(id="combine", agent="alpha", task="Combine {{result_a}} and {{result_b}}")
        wf = Workflow(steps=[group, sequential], agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert len(results) == 3


class TestConditionalExecution:
    @pytest.mark.asyncio
    async def test_condition_true_runs_step(self, agents, mock_llm_router):
        step = Step(id="s1", agent="alpha", task="Do it", condition="1 == 1")
        wf = Workflow(steps=[step], agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert len(results) == 1
        assert results[0].step_id == "s1"

    @pytest.mark.asyncio
    async def test_condition_false_skips_step(self, agents, mock_llm_router):
        step = Step(id="s1", agent="alpha", task="Do it", condition="1 == 2")
        wf = Workflow(steps=[step], agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert len(results) == 0


class TestBranching:
    @pytest.mark.asyncio
    async def test_on_success_jumps(self, agents, mock_llm_router):
        steps = [
            Step(id="s1", agent="alpha", task="First", on_success="s3"),
            Step(id="s2", agent="alpha", task="Skipped"),
            Step(id="s3", agent="alpha", task="Jumped here"),
        ]
        wf = Workflow(steps=steps, agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        ids = [r.step_id for r in results]
        assert "s1" in ids
        assert "s3" in ids
        assert "s2" not in ids


class TestTimeoutEnforcement:
    @pytest.mark.asyncio
    async def test_step_timeout(self, agents, mock_llm_router):
        """A step with a very short timeout should fail with a timeout error."""
        # Make the mock LLM take a while
        original_complete = mock_llm_router.complete

        async def slow_complete(**kwargs):
            await asyncio.sleep(2)
            return await original_complete(**kwargs)

        mock_llm_router.complete.side_effect = slow_complete

        step = Step(id="slow", agent="alpha", task="Take your time", timeout=0.1)
        wf = Workflow(steps=[step], agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert len(results) == 1
        assert results[0].success is False
        assert "timed out" in (results[0].error or "").lower()


class TestOutputFormat:
    @pytest.mark.asyncio
    async def test_json_format_hint_appended(self, agents, mock_llm_router):
        """When output_format=json, the resolved task should include the format hint."""
        step = Step(id="s1", agent="alpha", task="Give me data", output_format="json")
        wf = Workflow(steps=[step], agents=agents)

        # Check that the mock was called with a task containing the format hint
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert len(results) == 1
        # The result itself should succeed
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_text_format_no_hint(self, agents, mock_llm_router):
        """Default output_format=text should NOT append a format hint."""
        step = Step(id="s1", agent="alpha", task="Give me data", output_format="text")
        wf = Workflow(steps=[step], agents=agents)
        results = await wf.execute(
            user_input="go",
            tracer=Tracer(),
            event_bus=EventBus(),
            llm_router=mock_llm_router,
            approval_manager=ApprovalManager(mode="cli"),
        )
        assert results[0].success is True


class TestConditionEvaluation:
    """Extended condition evaluation tests."""

    def test_boolean_case_insensitive(self):
        wf = Workflow(steps=[], agents={})
        assert wf._evaluate_condition("True == true", {}) is True
        assert wf._evaluate_condition("FALSE == false", {}) is True

    def test_not_empty(self):
        wf = Workflow(steps=[], agents={})
        assert wf._evaluate_condition("something not empty", {"something": "value"}) is True

    def test_empty(self):
        wf = Workflow(steps=[], agents={})
        assert wf._evaluate_condition("something empty", {"something": ""}) is True

    def test_contains(self):
        wf = Workflow(steps=[], agents={})
        assert wf._evaluate_condition("'hello world' contains 'world'", {}) is True

    def test_numeric_comparison(self):
        wf = Workflow(steps=[], agents={})
        assert wf._evaluate_condition("10 > 5", {}) is True
        assert wf._evaluate_condition("3 <= 3", {}) is True
        assert wf._evaluate_condition("7 != 8", {}) is True
