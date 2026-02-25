"""Shared fixtures for AgentForge tests."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from agentforge.core.agent import Agent
from agentforge.core.team import Team
from agentforge.llm.router import LLMRouter
from agentforge.llm.provider import LLMResponse
from agentforge.observe.tracer import Tracer
from agentforge.observe.events import EventBus
from agentforge.control.approval import ApprovalManager
from agentforge.tools.base import Tool


@pytest.fixture
def sample_config():
    """Minimal valid configuration dict."""
    return {
        "team": {
            "name": "Test Team",
            "llm": "openai/gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 4096,
            "memory": {
                "enabled": False,
                "backend": "sqlite",
                "path": ".agentforge/test_memory.db",
                "shared": True,
            },
            "observe": {
                "trace": True,
                "cost_tracking": True,
                "log_level": "info",
                "log_format": "pretty",
            },
            "control": {
                "dry_run": False,
                "max_retries": 3,
                "timeout": 300,
                "confidence_threshold": 0.4,
            },
        },
        "agents": {
            "assistant": {
                "role": "Helpful Assistant",
                "goal": "Answer questions accurately",
            },
        },
        "workflow": {
            "steps": [
                {
                    "id": "answer",
                    "agent": "assistant",
                    "task": "{{input}}",
                }
            ],
        },
    }


@pytest.fixture
def sample_agent():
    """A simple test agent."""
    return Agent(
        name="test_agent",
        role="Test Role",
        goal="Test Goal",
    )


@pytest.fixture
def sample_team(sample_agent):
    """A simple test team."""
    return Team(
        name="Test Team",
        agents={"test_agent": sample_agent},
    )


@pytest.fixture
def mock_llm_router():
    """A mock LLM router that returns canned responses."""
    router = MagicMock(spec=LLMRouter)
    router.default_model = "openai/gpt-4o-mini"
    router.total_tokens = {"input": 0, "output": 0}
    router.total_cost = 0.0
    router.call_log = []

    async def mock_complete(**kwargs):
        return LLMResponse(
            content="This is a test response.",
            tool_calls=[],
            model_used="openai/gpt-4o-mini",
            input_tokens=50,
            output_tokens=20,
            cost=0.001,
            latency_ms=100,
        )

    router.complete = AsyncMock(side_effect=mock_complete)
    router.get_cost_summary = MagicMock(return_value={
        "total_cost": 0.001,
        "total_tokens": {"input": 50, "output": 20},
        "by_model": {},
        "call_count": 1,
    })
    return router


@pytest.fixture
def tracer():
    """A fresh tracer instance."""
    return Tracer()


@pytest.fixture
def event_bus():
    """A fresh event bus instance."""
    return EventBus()


@pytest.fixture
def approval_manager():
    """An approval manager in CLI mode."""
    return ApprovalManager(mode="cli")


@pytest.fixture
def sample_tool():
    """A simple test tool."""
    async def handler(query: str) -> str:
        return f"Result for: {query}"

    return Tool(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Test query"},
            },
            "required": ["query"],
        },
        handler=handler,
    )
