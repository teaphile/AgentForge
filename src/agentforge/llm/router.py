"""LLM routing with fallback chains and cost tracking via litellm."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import litellm
from litellm import acompletion

from agentforge.llm.provider import LLMError, LLMResponse

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True


@dataclass
class CallRecord:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    error: str | None = None


class LLMRouter:

    def __init__(self, default_model: str = "openai/gpt-4o-mini", cost_tracking: bool = True):
        self.default_model = default_model
        self.cost_tracking = cost_tracking
        self.total_tokens = {"input": 0, "output": 0}
        self.total_cost = 0.0
        self.call_log: list[CallRecord] = []

    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        fallback: list[str] | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        models_to_try = [model or self.default_model] + (fallback or [])
        errors: list[str] = []

        for current_model in models_to_try:
            max_retries = 3
            for attempt in range(max_retries):
                start_ms = time.time() * 1000
                try:
                    kwargs: dict[str, Any] = {
                        "model": current_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if tools:
                        kwargs["tools"] = tools
                        kwargs["tool_choice"] = "auto"

                    response = await acompletion(**kwargs)

                    latency_ms = time.time() * 1000 - start_ms

                    # Extract response data
                    choice = response.choices[0]
                    content = choice.message.content
                    tool_calls_raw = choice.message.tool_calls or []

                    # Parse tool calls
                    parsed_tool_calls = []
                    for tc in tool_calls_raw:
                        try:
                            args = (
                                json.loads(tc.function.arguments)
                                if isinstance(tc.function.arguments, str)
                                else tc.function.arguments
                            )
                        except (ValueError, AttributeError):
                            args = {}
                        parsed_tool_calls.append(
                            {
                                "id": tc.id,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": args,
                                },
                            }
                        )

                    # Token usage
                    usage = getattr(response, "usage", None)
                    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
                    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

                    # Cost calculation
                    cost = 0.0
                    if self.cost_tracking:
                        try:
                            cost = litellm.completion_cost(completion_response=response)
                        except Exception:
                            cost = 0.0

                    # Update totals
                    self.total_tokens["input"] += input_tokens
                    self.total_tokens["output"] += output_tokens
                    self.total_cost += cost

                    # Log
                    self.call_log.append(
                        CallRecord(
                            model=current_model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cost=cost,
                            latency_ms=latency_ms,
                            success=True,
                        )
                    )

                    return LLMResponse(
                        content=content,
                        tool_calls=parsed_tool_calls,
                        model_used=current_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost,
                        latency_ms=latency_ms,
                    )

                except Exception as e:
                    error_name = type(e).__name__
                    error_str = f"{current_model} (attempt {attempt + 1}): {error_name}: {e}"
                    errors.append(error_str)

                    self.call_log.append(
                        CallRecord(
                            model=current_model,
                            latency_ms=time.time() * 1000 - start_ms,
                            success=False,
                            error=error_str,
                        )
                    )

                    # Rate limit → backoff and retry
                    is_rate_limit = "rate" in str(e).lower() or "429" in str(e)
                    if is_rate_limit and attempt < max_retries - 1:
                        wait = 2**attempt
                        await asyncio.sleep(wait)
                        continue
                    else:
                        break

        raise LLMError(
            f"All models failed. Tried: {models_to_try}. Errors: {errors}",
            models_tried=models_to_try,
            errors=errors,
        )

    def get_cost_summary(self) -> dict:
        by_model: dict[str, dict] = {}
        for record in self.call_log:
            if record.model not in by_model:
                by_model[record.model] = {"cost": 0.0, "tokens": {"input": 0, "output": 0}, "calls": 0}
            by_model[record.model]["cost"] += record.cost
            by_model[record.model]["tokens"]["input"] += record.input_tokens
            by_model[record.model]["tokens"]["output"] += record.output_tokens
            by_model[record.model]["calls"] += 1

        return {
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens.copy(),
            "by_model": by_model,
            "call_count": len(self.call_log),
        }
