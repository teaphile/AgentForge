"""Tests for the Workflow engine."""

from __future__ import annotations

import pytest

from agentforge.core.workflow import Workflow
from agentforge.core.step import Step
from agentforge.core.agent import Agent
from agentforge.observe.tracer import Tracer
from agentforge.observe.events import EventBus
from agentforge.control.approval import ApprovalManager


@pytest.fixture
def helper_agent():
    return Agent(name="helper", role="Helper", goal="Help")


@pytest.fixture
def simple_workflow(helper_agent):
    steps = [Step(id="step1", agent="helper", task="Do the thing")]
    return Workflow(steps=steps, agents={"helper": helper_agent})


@pytest.fixture
def multi_step_workflow(helper_agent):
    steps = [
        Step(id="step1", agent="helper", task="Research {{input}}"),
        Step(id="step2", agent="helper", task="Write about {{step1}}"),
    ]
    return Workflow(steps=steps, agents={"helper": helper_agent})


class TestWorkflowCreation:
    def test_basic_workflow(self, simple_workflow):
        assert len(simple_workflow.steps) == 1

    def test_multi_step(self, multi_step_workflow):
        assert len(multi_step_workflow.steps) == 2


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_simple_execution(self, simple_workflow, mock_llm_router):
        tracer = Tracer()
        event_bus = EventBus()
        approval = ApprovalManager(mode="cli")

        results = await simple_workflow.execute(
            user_input="test",
            tracer=tracer,
            event_bus=event_bus,
            llm_router=mock_llm_router,
            approval_manager=approval,
        )
        assert isinstance(results, list)
        assert len(results) >= 1


class TestResolveTemplate:
    def test_basic_interpolation(self, helper_agent):
        wf = Workflow(steps=[], agents={"helper": helper_agent})
        result = wf._resolve_template("Hello {{name}}", {"name": "World"})
        assert result == "Hello World"

    def test_missing_variable_kept(self, helper_agent):
        wf = Workflow(steps=[], agents={"helper": helper_agent})
        result = wf._resolve_template("Hello {{name}}", {})
        assert "{{name}}" in result

    def test_multiple_variables(self, helper_agent):
        wf = Workflow(steps=[], agents={"helper": helper_agent})
        result = wf._resolve_template("{{a}} and {{b}}", {"a": "X", "b": "Y"})
        assert result == "X and Y"


class TestConditionEvaluation:
    def test_simple_condition(self, helper_agent):
        wf = Workflow(steps=[], agents={"helper": helper_agent})
        assert wf._evaluate_condition("len('abc') > 0", {"input": "test"}) is True

    def test_false_condition(self, helper_agent):
        wf = Workflow(steps=[], agents={"helper": helper_agent})
        assert wf._evaluate_condition("1 > 2", {}) is False
