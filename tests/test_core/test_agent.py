"""Tests for the Agent class."""

from __future__ import annotations

import pytest

from agentforge.core.agent import Agent
from agentforge.core.result import AgentResult
from agentforge.observe.tracer import Tracer
from agentforge.observe.events import EventBus


class TestAgentCreation:
    def test_basic_agent(self):
        agent = Agent(name="writer", role="Writer", goal="Write well")
        assert agent.name == "writer"
        assert agent.role == "Writer"
        assert agent.goal == "Write well"

    def test_agent_defaults(self):
        agent = Agent(name="a", role="R", goal="G")
        assert agent.tools == [] or agent.tools is not None

    def test_from_config(self):
        config = {
            "role": "Researcher",
            "goal": "Find accurate information",
            "backstory": "Expert researcher",
            "tools": [],
        }
        team_config = {"llm": "openai/gpt-4o-mini", "temperature": 0.7, "max_tokens": 4096}
        agent = Agent.from_config("researcher", config, team_config)
        assert agent.name == "researcher"
        assert agent.role == "Researcher"


class TestAgentExecution:
    @pytest.mark.asyncio
    async def test_execute_simple_task(self, mock_llm_router):
        agent = Agent(name="test", role="Helper", goal="Help")
        tracer = Tracer()
        event_bus = EventBus()
        result = await agent.execute(
            task="Hello world",
            context={},
            llm_router=mock_llm_router,
            tracer=tracer,
            event_bus=event_bus,
        )
        assert result is not None
        assert isinstance(result, AgentResult)

    @pytest.mark.asyncio
    async def test_execute_with_context(self, mock_llm_router):
        agent = Agent(name="test", role="Helper", goal="Help")
        tracer = Tracer()
        event_bus = EventBus()
        result = await agent.execute(
            task="Summarize this",
            context={"previous": "Some prior work"},
            llm_router=mock_llm_router,
            tracer=tracer,
            event_bus=event_bus,
        )
        assert result is not None


class TestAgentSystemPrompt:
    def test_system_prompt_includes_role(self):
        agent = Agent(name="w", role="Expert Writer", goal="Write great content")
        prompt = agent._build_system_prompt()
        assert "Expert Writer" in prompt

    def test_system_prompt_includes_goal(self):
        agent = Agent(name="w", role="Writer", goal="Write amazing content")
        prompt = agent._build_system_prompt()
        assert "Write amazing content" in prompt
