"""Tests for LLM provider models."""

from __future__ import annotations


from agentforge.llm.provider import LLMResponse, LLMError


class TestLLMResponse:
    def test_basic_response(self):
        resp = LLMResponse(
            content="Hello world",
            tool_calls=[],
            model_used="openai/gpt-4o-mini",
            input_tokens=10,
            output_tokens=5,
            cost=0.001,
            latency_ms=150,
        )
        assert resp.content == "Hello world"
        assert resp.model_used == "openai/gpt-4o-mini"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.cost == 0.001

    def test_response_with_tool_calls(self):
        tool_calls = [
            {"id": "call_1", "function": {"name": "web_search", "arguments": '{"query": "test"}'}},
        ]
        resp = LLMResponse(
            content=None,
            tool_calls=tool_calls,
            model_used="openai/gpt-4o",
            input_tokens=50,
            output_tokens=30,
            cost=0.005,
            latency_ms=200,
        )
        assert resp.content is None
        assert len(resp.tool_calls) == 1

    def test_response_zero_cost(self):
        resp = LLMResponse(
            content="Free",
            tool_calls=[],
            model_used="ollama/llama3",
            input_tokens=10,
            output_tokens=5,
            cost=0.0,
            latency_ms=50,
        )
        assert resp.cost == 0.0


class TestLLMError:
    def test_basic_error(self):
        err = LLMError(
            "Rate limited",
            models_tried=["openai/gpt-4o"],
            errors=["429 Too Many Requests"],
        )
        assert "Rate limited" in str(err)
        assert len(err.models_tried) == 1

    def test_error_defaults(self):
        err = LLMError("Connection failed")
        assert "Connection failed" in str(err)
        assert err.models_tried == []
        assert err.errors == []
