"""Tests for LLM Router."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from agentforge.llm.router import LLMRouter


class TestLLMRouterInit:
    def test_basic_init(self):
        router = LLMRouter(default_model="openai/gpt-4o-mini")
        assert router.default_model == "openai/gpt-4o-mini"

    def test_with_cost_tracking(self):
        router = LLMRouter(
            default_model="openai/gpt-4o",
            cost_tracking=True,
        )
        assert router.cost_tracking is True

    def test_default_model(self):
        router = LLMRouter()
        assert router.default_model == "openai/gpt-4o-mini"


class TestLLMRouterComplete:
    @pytest.mark.asyncio
    @patch("agentforge.llm.router.acompletion")
    @patch("agentforge.llm.router.litellm")
    async def test_successful_completion(self, mock_litellm, mock_acompletion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "openai/gpt-4o-mini"
        mock_acompletion.return_value = mock_response
        mock_litellm.completion_cost = MagicMock(return_value=0.0001)

        router = LLMRouter(default_model="openai/gpt-4o-mini")
        result = await router.complete(
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result.content == "Hello!"
        assert result.input_tokens == 10

    @pytest.mark.asyncio
    @patch("agentforge.llm.router.acompletion")
    @patch("agentforge.llm.router.litellm")
    async def test_cost_tracking(self, mock_litellm, mock_acompletion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.model = "openai/gpt-4o"
        mock_acompletion.return_value = mock_response
        mock_litellm.completion_cost = MagicMock(return_value=0.01)

        router = LLMRouter(default_model="openai/gpt-4o")
        await router.complete(messages=[{"role": "user", "content": "Test"}])

        summary = router.get_cost_summary()
        assert summary["total_cost"] > 0
        assert summary["call_count"] >= 1


class TestLLMRouterCostSummary:
    def test_empty_summary(self):
        router = LLMRouter(default_model="openai/gpt-4o-mini")
        summary = router.get_cost_summary()
        assert summary["total_cost"] == 0
        assert summary["call_count"] == 0
