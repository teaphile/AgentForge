"""Tests for config schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentforge.config.schema import (
    ForgeConfig,
    TeamConfig,
    AgentConfig,
    WorkflowConfig,
    StepConfig,
    MemoryConfig,
    ObserveConfig,
    ControlConfig,
)


class TestTeamConfig:
    def test_valid_team(self):
        team = TeamConfig(name="Test", llm="openai/gpt-4o-mini")
        assert team.name == "Test"
        assert team.llm == "openai/gpt-4o-mini"

    def test_defaults(self):
        team = TeamConfig(name="T")
        assert team.temperature is not None or team.temperature == 0
        assert team.max_tokens is not None or team.max_tokens == 0

    def test_memory_config_defaults(self):
        mem = MemoryConfig()
        assert mem.enabled is not None
        assert mem.backend is not None


class TestAgentConfig:
    def test_valid_agent(self):
        agent = AgentConfig(role="Writer", goal="Write well")
        assert agent.role == "Writer"
        assert agent.goal == "Write well"

    def test_agent_with_tools(self):
        agent = AgentConfig(role="R", goal="G", tools=["web_search", "calculator"])
        assert len(agent.tools) == 2


class TestStepConfig:
    def test_valid_step(self):
        step = StepConfig(id="step1", agent="writer", task="Write something")
        assert step.id == "step1"
        assert step.agent == "writer"

    def test_step_with_all_options(self):
        step = StepConfig(
            id="step1",
            agent="writer",
            task="Write",
            timeout=60,
            retry_on_fail=True,
            approval_gate=True,
            dry_run=False,
            save_as="result",
        )
        assert step.approval_gate
        assert step.retry_on_fail


class TestWorkflowConfig:
    def test_valid_workflow(self):
        wf = WorkflowConfig(steps=[StepConfig(id="s1", agent="a", task="t")])
        assert len(wf.steps) == 1


class TestObserveConfig:
    def test_defaults(self):
        obs = ObserveConfig()
        assert obs.trace is not None
        assert obs.cost_tracking is not None


class TestControlConfig:
    def test_defaults(self):
        ctrl = ControlConfig()
        assert ctrl.dry_run is not None
        assert ctrl.max_retries is not None


class TestForgeConfig:
    def test_valid_full_config(self, sample_config):
        config = ForgeConfig(**sample_config)
        assert config.team.name == "Test Team"
        assert "assistant" in config.agents
        assert len(config.workflow.steps) == 1

    def test_missing_team_raises(self):
        with pytest.raises(ValidationError):
            ForgeConfig(agents={"a": AgentConfig(role="R", goal="G")}, workflow=WorkflowConfig(steps=[]))

    def test_missing_agents_raises(self):
        with pytest.raises(ValidationError):
            ForgeConfig(team=TeamConfig(name="T"), workflow=WorkflowConfig(steps=[]))
