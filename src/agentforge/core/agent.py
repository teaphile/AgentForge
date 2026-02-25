"""ReAct-loop agent with tools and memory."""

from __future__ import annotations

import json
import time
from typing import Any

from agentforge.core.result import AgentResult, TokenUsage, ToolCallRecord
from agentforge.control.confidence import ConfidenceChecker
from agentforge.control.dry_run import DryRunController
from agentforge.control.guardrails import Guardrails
from agentforge.llm.provider import LLMResponse
from agentforge.observe.tracer import EventType, TraceEvent


class Agent:


    def __init__(
        self,
        name: str,
        role: str,
        goal: str,
        backstory: str = "",
        llm: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        fallback: list[str] | None = None,
        tools: list | None = None,
        memory: Any = None,
        instructions: str = "",
        control: dict | None = None,
    ):
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.llm = llm
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.fallback = fallback or []
        self.tools = tools or []
        self.memory = memory
        self.instructions = instructions
        self.control = control or {}
        self.guardrails = Guardrails(
            allowed_actions=self.control.get("allowed_actions", []),
            blocked_actions=self.control.get("blocked_actions", []),
        )

    async def execute(
        self,
        task: str,
        context: dict,
        llm_router: Any,
        tracer: Any,
        event_bus: Any,
        dry_run: bool = False,
    ) -> AgentResult:
        start_time = time.time()
        total_tokens = TokenUsage()
        total_cost = 0.0
        all_tool_calls: list[ToolCallRecord] = []
        model_used = ""

        max_iterations = self.control.get("max_iterations", 10)

        memory_context = ""
        if self.memory:
            try:
                recall_limit = self.control.get("recall_limit", 10)
                memories = await self.memory.recall(self.name, task, limit=recall_limit)
                if memories:
                    memory_context = "\n".join(
                        f"- {m['content']}" for m in memories
                    )
                    tracer.record(
                        TraceEvent(
                            event_type=EventType.MEMORY_RECALL,
                            agent_name=self.name,
                            data={"memories_count": len(memories)},
                        )
                    )
            except Exception as exc:
                tracer.record(
                    TraceEvent(
                        event_type=EventType.ERROR,
                        agent_name=self.name,
                        data={"error": f"memory recall failed: {exc}"},
                    )
                )

        system_prompt = self._build_system_prompt(memory_context)
        formatted_tools = self._format_tools_for_llm() if self.tools else None

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        for iteration in range(max_iterations):
            # Emit thinking event
            await event_bus.emit(
                TraceEvent(
                    event_type=EventType.AGENT_THINKING,
                    agent_name=self.name,
                    data={"iteration": iteration + 1, "model": self.llm or llm_router.default_model},
                )
            )

            # Call LLM
            try:
                response: LLMResponse = await llm_router.complete(
                    messages=messages,
                    model=self.llm,
                    fallback=self.fallback if self.fallback else None,
                    tools=formatted_tools,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except Exception as e:
                duration = time.time() - start_time
                tracer.record(
                    TraceEvent(
                        event_type=EventType.ERROR,
                        agent_name=self.name,
                        data={"error": str(e)},
                    )
                )
                return AgentResult(
                    output="",
                    success=False,
                    tokens=total_tokens,
                    cost=total_cost,
                    tool_calls=all_tool_calls,
                    iterations=iteration + 1,
                    duration=duration,
                    error=str(e),
                )

            model_used = response.model_used
            total_tokens.input_tokens += response.input_tokens
            total_tokens.output_tokens += response.output_tokens
            total_cost += response.cost

            # Emit response event
            tracer.record(
                TraceEvent(
                    event_type=EventType.AGENT_RESPONSE,
                    agent_name=self.name,
                    data={
                        "model": model_used,
                        "has_tool_calls": bool(response.tool_calls),
                        "content_preview": (response.content or "")[:200],
                    },
                    tokens={"input": response.input_tokens, "output": response.output_tokens},
                    cost=response.cost,
                )
            )
            await event_bus.emit(
                TraceEvent(
                    event_type=EventType.AGENT_RESPONSE,
                    agent_name=self.name,
                    data={
                        "model": model_used,
                        "has_tool_calls": bool(response.tool_calls),
                    },
                    tokens={"input": response.input_tokens, "output": response.output_tokens},
                    cost=response.cost,
                )
            )

            # Handle tool calls
            if response.tool_calls:
                # Build the assistant message with tool calls for the conversation
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": (
                                    json.dumps(tc["function"]["arguments"])
                                    if isinstance(tc["function"]["arguments"], dict)
                                    else tc["function"]["arguments"]
                                ),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args = tc["function"]["arguments"]
                    tool_call_id = tc["id"]

                    # Guardrails check
                    if not self.guardrails.is_tool_allowed(tool_name):
                        tool_result_str = f"Tool '{tool_name}' is not allowed by guardrails."
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_result_str,
                        })
                        continue

                    tc_start = time.time()

                    if dry_run:
                        dry_controller = DryRunController(enabled=True)
                        result = dry_controller.simulate_tool(tool_name, tool_args)
                    else:
                        # Find and execute the tool
                        result = None
                        for t in self.tools:
                            if t.name == tool_name:
                                result = await t.execute(**tool_args)
                                break
                        if result is None:
                            from agentforge.tools.base import ToolResult

                            result = ToolResult(
                                success=False,
                                output="",
                                error=f"Tool '{tool_name}' not found",
                            )

                    tc_duration = (time.time() - tc_start) * 1000

                    record = ToolCallRecord(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=result.output,
                        success=result.success,
                        duration_ms=tc_duration,
                    )
                    all_tool_calls.append(record)

                    # Emit tool events
                    tracer.record(
                        TraceEvent(
                            event_type=EventType.TOOL_CALL,
                            agent_name=self.name,
                            data={
                                "tool": tool_name,
                                "args": tool_args,
                                "dry_run": dry_run,
                            },
                        )
                    )
                    tracer.record(
                        TraceEvent(
                            event_type=EventType.TOOL_RESULT,
                            agent_name=self.name,
                            data={
                                "tool": tool_name,
                                "success": result.success,
                                "output_preview": result.output[:300],
                            },
                            duration_ms=tc_duration,
                        )
                    )
                    await event_bus.emit(
                        TraceEvent(
                            event_type=EventType.TOOL_CALL,
                            agent_name=self.name,
                            data={"tool": tool_name, "success": result.success},
                            duration_ms=tc_duration,
                        )
                    )

                    # Append tool result to messages
                    tool_result_str = result.output if result.success else f"Error: {result.error}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result_str,
                    })

                # Continue the ReAct loop
                continue

            # No tool calls — final answer
            output = response.content or ""

            # Confidence scoring
            confidence_threshold = self.control.get("confidence_threshold", 0.0)
            if confidence_threshold > 0:
                checker = ConfidenceChecker(threshold=confidence_threshold)
                score = checker.check(output)
                tracer.record(
                    TraceEvent(
                        event_type=EventType.AGENT_RESPONSE,
                        agent_name=self.name,
                        data={"confidence_score": score, "threshold": confidence_threshold},
                    )
                )
                if score < confidence_threshold and iteration < max_iterations - 1:
                    # Below threshold — ask the LLM to elaborate
                    messages.append({"role": "assistant", "content": output})
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous answer scored low on confidence. "
                            "Please provide a more detailed, definitive response."
                        ),
                    })
                    continue

            if self.memory:
                try:
                    summary = output[:500] if len(output) > 500 else output
                    await self.memory.store(
                        self.name,
                        f"Task: {task[:200]}\nResult: {summary}",
                        importance=0.6,
                    )
                    tracer.record(
                        TraceEvent(
                            event_type=EventType.MEMORY_STORE,
                            agent_name=self.name,
                            data={"stored_length": len(summary)},
                        )
                    )
                except Exception as exc:
                    tracer.record(
                        TraceEvent(
                            event_type=EventType.ERROR,
                            agent_name=self.name,
                            data={"error": f"memory store failed: {exc}"},
                        )
                    )

            duration = time.time() - start_time
            return AgentResult(
                output=output,
                success=True,
                tokens=total_tokens,
                cost=total_cost,
                tool_calls=all_tool_calls,
                iterations=iteration + 1,
                duration=duration,
                model_used=model_used,
            )

        # Max iterations exhausted without a final answer
        duration = time.time() - start_time
        last_content = messages[-1].get("content", "") if messages else ""
        return AgentResult(
            output=last_content if isinstance(last_content, str) else str(last_content),
            success=False,
            tokens=total_tokens,
            cost=total_cost,
            tool_calls=all_tool_calls,
            iterations=max_iterations,
            duration=duration,
            model_used=model_used,
        )

    def _build_system_prompt(self, memory_context: str = "") -> str:
        parts = [f"You are {self.role}.", f"\nYour goal: {self.goal}"]

        if self.backstory:
            parts.append(f"\n{self.backstory}")

        if self.instructions:
            parts.append(f"\n{self.instructions}")

        if self.tools:
            tool_descriptions = []
            for t in self.tools:
                params_desc = ""
                if t.parameters and "properties" in t.parameters:
                    params_list = []
                    for pname, pinfo in t.parameters["properties"].items():
                        ptype = pinfo.get("type", "string")
                        pdesc = pinfo.get("description", "")
                        params_list.append(f"    - {pname} ({ptype}): {pdesc}")
                    params_desc = "\n".join(params_list)
                tool_descriptions.append(f"  • {t.name}: {t.description}\n{params_desc}")

            parts.append("\nYou have access to the following tools:\n" + "\n".join(tool_descriptions))

        if memory_context:
            parts.append(f"\nHere is relevant context from previous work:\n{memory_context}")

        parts.append(
            "\nGuidelines:\n"
            "- Use tools when you need external information or actions.\n"
            "- When you have enough information, respond directly without tool calls.\n"
            "- Be precise and factual."
        )

        return "\n".join(parts)

    def _format_tools_for_llm(self) -> list[dict]:
        formatted = []
        for t in self.tools:
            if not self.guardrails.is_tool_allowed(t.name):
                continue
            formatted.append(t.to_openai_schema())
        return formatted

    @classmethod
    def from_config(cls, name: str, agent_config: dict, team_config: dict) -> "Agent":
        from agentforge.tools.registry import get_registry
        from agentforge.memory.short_term import ShortTermMemory
        from agentforge.memory.long_term import LongTermMemory

        registry = get_registry()

        # Resolve tools
        tool_specs = agent_config.get("tools", [])
        tools = registry.resolve_tools(tool_specs) if tool_specs else []

        # Resolve memory
        memory = None
        mem_config = agent_config.get("memory", {})
        team_mem_config = team_config.get("memory", {})
        if mem_config.get("enabled", team_mem_config.get("enabled", True)):
            mem_type = mem_config.get("type", "short_term")
            if mem_type == "long_term":
                db_path = team_mem_config.get("path", ".agentforge/memory.db")
                shared = team_mem_config.get("shared", True)
                memory = LongTermMemory(db_path=db_path, shared=shared)
            else:
                memory = ShortTermMemory(shared=team_mem_config.get("shared", True))

        return cls(
            name=name,
            role=agent_config["role"],
            goal=agent_config["goal"],
            backstory=agent_config.get("backstory", ""),
            llm=agent_config.get("llm"),
            temperature=agent_config.get("temperature", team_config.get("temperature", 0.7)),
            max_tokens=agent_config.get("max_tokens", team_config.get("max_tokens", 4096)),
            fallback=agent_config.get("fallback", []),
            tools=tools,
            memory=memory,
            instructions=agent_config.get("instructions", ""),
            control=agent_config.get("control", {}),
        )
