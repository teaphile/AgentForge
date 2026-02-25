"""DAG-based workflow execution engine."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from agentforge.core.step import ParallelGroup, Step
from agentforge.core.result import StepResult
from agentforge.observe.tracer import EventType, TraceEvent


class Workflow:

    def __init__(self, steps: list, agents: dict, control_config: dict | None = None):
        self.steps = steps
        self.agents = agents
        self.control_config = control_config or {}

    @classmethod
    def from_config(cls, config: dict, team: Any) -> "Workflow":
        workflow_config = config.get("workflow", {})
        steps_config = workflow_config.get("steps", [])

        steps = []
        for step_item in steps_config:
            if isinstance(step_item, dict) and "parallel" in step_item:
                group = ParallelGroup.from_config(step_item["parallel"])
                steps.append(group)
            elif isinstance(step_item, dict):
                steps.append(Step.from_config(step_item))

        control_config = config.get("team", {}).get("control", {})
        return cls(steps=steps, agents=team.agents, control_config=control_config)

    async def execute(
        self,
        user_input: str,
        tracer: Any,
        event_bus: Any,
        llm_router: Any,
        approval_manager: Any,
        dry_run: bool = False,
    ) -> list[StepResult]:
        context: dict[str, Any] = {
            "input": user_input,
        }

        step_results: list[StepResult] = []
        step_index = 0
        step_map: dict[str, int] = {}  # step_id → index in self.steps

        for i, item in enumerate(self.steps):
            if isinstance(item, Step):
                step_map[item.id] = i
            elif isinstance(item, ParallelGroup):
                for s in item.steps:
                    step_map[s.id] = i

        total_steps = len(self.steps)
        visited: dict[str, int] = {}  # step_id → visit count (for loop control)
        max_retries = self.control_config.get("max_retries", 3)

        while step_index < total_steps:
            item = self.steps[step_index]

            if isinstance(item, ParallelGroup):
                # Execute all steps in parallel
                parallel_results = await self._execute_parallel(
                    item, context, tracer, event_bus, llm_router, approval_manager, dry_run,
                    step_index + 1, total_steps,
                )
                step_results.extend(parallel_results)
                step_index += 1
                continue

            # Sequential step
            step: Step = item

            # Track visits for loop control
            visited[step.id] = visited.get(step.id, 0) + 1
            if visited[step.id] > max_retries + 1:
                step_index += 1
                continue

            # Evaluate condition
            if step.condition:
                resolved_condition = self._resolve_template(step.condition, context)
                if not self._evaluate_condition(resolved_condition, context):
                    step_index += 1
                    continue

            # Resolve task template
            resolved_task = self._resolve_template(step.task, context)

            # Append output_format hint so the agent knows the expected format
            if step.output_format and step.output_format != "text":
                resolved_task += f"\n\n[Respond in {step.output_format} format.]"

            # Get agent
            agent = self.agents.get(step.agent)
            if not agent:
                step_results.append(
                    StepResult(
                        step_id=step.id,
                        agent_name=step.agent,
                        output="",
                        success=False,
                        error=f"Agent '{step.agent}' not found",
                    )
                )
                step_index += 1
                continue

            # Emit step start
            tracer.record(
                TraceEvent(
                    event_type=EventType.STEP_START,
                    step_id=step.id,
                    agent_name=step.agent,
                    data={"task": resolved_task, "step_num": step_index + 1, "total_steps": total_steps},
                )
            )
            await event_bus.emit(
                TraceEvent(
                    event_type=EventType.STEP_START,
                    step_id=step.id,
                    agent_name=step.agent,
                    data={"task": resolved_task, "step_num": step_index + 1, "total_steps": total_steps},
                )
            )

            # Determine dry_run for this step
            step_dry_run = step.dry_run if step.dry_run is not None else dry_run

            # Execute agent with optional timeout
            step_start = time.time()
            step_timeout = step.timeout
            if step_timeout is None:
                step_timeout = self.control_config.get("timeout")

            try:
                coro = agent.execute(
                    task=resolved_task,
                    context=context,
                    llm_router=llm_router,
                    tracer=tracer,
                    event_bus=event_bus,
                    dry_run=step_dry_run,
                )
                if step_timeout:
                    agent_result = await asyncio.wait_for(
                        coro, timeout=step_timeout,
                    )
                else:
                    agent_result = await coro
            except asyncio.TimeoutError:
                from agentforge.core.result import AgentResult, TokenUsage

                agent_result = AgentResult(
                    output="",
                    success=False,
                    tokens=TokenUsage(),
                    cost=0.0,
                    error=f"Step '{step.id}' timed out after {step_timeout}s",
                )
            step_duration = time.time() - step_start

            step_result = StepResult(
                step_id=step.id,
                agent_name=step.agent,
                output=agent_result.output,
                success=agent_result.success,
                tokens=agent_result.tokens,
                cost=agent_result.cost,
                tool_calls=agent_result.tool_calls,
                iterations=agent_result.iterations,
                duration=step_duration,
                model_used=agent_result.model_used,
                error=agent_result.error,
            )

            # Store in context
            context[step.id] = {
                "output": agent_result.output,
                "cost": agent_result.cost,
                "tokens": agent_result.tokens.total,
                "success": agent_result.success,
            }

            if step.save_as:
                context[step.save_as] = agent_result.output

            # Emit step end
            tracer.record(
                TraceEvent(
                    event_type=EventType.STEP_END,
                    step_id=step.id,
                    agent_name=step.agent,
                    data={
                        "success": agent_result.success,
                        "output_preview": agent_result.output[:200],
                        "model": agent_result.model_used,
                    },
                    tokens={"input": agent_result.tokens.input_tokens, "output": agent_result.tokens.output_tokens},
                    cost=agent_result.cost,
                    duration_ms=step_duration * 1000,
                )
            )
            await event_bus.emit(
                TraceEvent(
                    event_type=EventType.STEP_END,
                    step_id=step.id,
                    agent_name=step.agent,
                    data={
                        "success": agent_result.success,
                        "model": agent_result.model_used,
                    },
                    tokens={"input": agent_result.tokens.input_tokens, "output": agent_result.tokens.output_tokens},
                    cost=agent_result.cost,
                    duration_ms=step_duration * 1000,
                )
            )

            # Approval gate
            if step.approval_gate and approval_manager:
                tracer.record(
                    TraceEvent(
                        event_type=EventType.APPROVAL_REQUESTED,
                        step_id=step.id,
                        agent_name=step.agent,
                    )
                )
                await event_bus.emit(
                    TraceEvent(
                        event_type=EventType.APPROVAL_REQUESTED,
                        step_id=step.id,
                        agent_name=step.agent,
                        data={"output_preview": agent_result.output[:500]},
                    )
                )

                approval = await approval_manager.request_approval(
                    step_id=step.id,
                    agent_name=step.agent,
                    task=resolved_task,
                    output=agent_result.output,
                )

                step_result.approved = approval.approved
                tracer.record(
                    TraceEvent(
                        event_type=EventType.APPROVAL_RECEIVED,
                        step_id=step.id,
                        data={"approved": approval.approved, "reason": approval.reason},
                    )
                )

                if approval.edited_output:
                    step_result.output = approval.edited_output
                    context[step.id]["output"] = approval.edited_output

                if not approval.approved:
                    step_result.success = False
                    # Handle on_fail branching
                    if step.on_fail and step.on_fail in step_map:
                        step_results.append(step_result)
                        step_index = step_map[step.on_fail]
                        continue

            step_results.append(step_result)

            # Handle retry on failure
            if not agent_result.success and step.retry_on_fail:
                retry_count = visited.get(step.id, 1) - 1
                if retry_count < (step.retry_on_fail or 0):
                    tracer.record(
                        TraceEvent(
                            event_type=EventType.RETRY,
                            step_id=step.id,
                            data={"retry_number": retry_count + 1},
                        )
                    )
                    continue  # Re-execute same step

            # Handle branching
            if agent_result.success and step.on_success and step.on_success in step_map:
                step_index = step_map[step.on_success]
                continue
            elif not agent_result.success and step.on_fail and step.on_fail in step_map:
                step_index = step_map[step.on_fail]
                continue

            # Handle loop (next → step_id)
            if step.next and step.next in step_map:
                step_index = step_map[step.next]
                continue

            step_index += 1

        return step_results

    async def _execute_parallel(
        self,
        group: ParallelGroup,
        context: dict,
        tracer: Any,
        event_bus: Any,
        llm_router: Any,
        approval_manager: Any,
        dry_run: bool,
        step_num: int,
        total_steps: int,
    ) -> list[StepResult]:

        async def _run_step(step: Step) -> StepResult:
            resolved_task = self._resolve_template(step.task, context)

            # Append output_format hint
            if step.output_format and step.output_format != "text":
                resolved_task += f"\n\n[Respond in {step.output_format} format.]"

            agent = self.agents.get(step.agent)
            if not agent:
                return StepResult(
                    step_id=step.id, agent_name=step.agent,
                    output="", success=False, error=f"Agent '{step.agent}' not found",
                )

            tracer.record(
                TraceEvent(
                    event_type=EventType.STEP_START, step_id=step.id,
                    agent_name=step.agent,
                    data={"task": resolved_task, "parallel": True},
                )
            )

            step_dry_run = step.dry_run if step.dry_run is not None else dry_run
            step_start = time.time()
            agent_result = await agent.execute(
                task=resolved_task, context=context,
                llm_router=llm_router, tracer=tracer, event_bus=event_bus,
                dry_run=step_dry_run,
            )
            step_duration = time.time() - step_start

            sr = StepResult(
                step_id=step.id, agent_name=step.agent,
                output=agent_result.output, success=agent_result.success,
                tokens=agent_result.tokens, cost=agent_result.cost,
                tool_calls=agent_result.tool_calls, iterations=agent_result.iterations,
                duration=step_duration, model_used=agent_result.model_used,
                error=agent_result.error,
            )

            context[step.id] = {
                "output": agent_result.output,
                "cost": agent_result.cost,
                "tokens": agent_result.tokens.total,
                "success": agent_result.success,
            }
            if step.save_as:
                context[step.save_as] = agent_result.output

            tracer.record(
                TraceEvent(
                    event_type=EventType.STEP_END, step_id=step.id,
                    agent_name=step.agent,
                    data={"success": agent_result.success, "parallel": True},
                    tokens={"input": agent_result.tokens.input_tokens, "output": agent_result.tokens.output_tokens},
                    cost=agent_result.cost, duration_ms=step_duration * 1000,
                )
            )
            return sr

        results = await asyncio.gather(*[_run_step(s) for s in group.steps])
        return list(results)

    def _resolve_template(self, template: str, context: dict) -> str:

        def _replacer(match: re.Match) -> str:
            path = match.group(1).strip()
            parts = path.split(".")

            current: Any = context
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return match.group(0)  # Leave unresolved if not found

            return str(current)

        return re.sub(r"\{\{([^}]+)\}\}", _replacer, template)

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """Evaluate a simple condition (==, !=, >, <, contains, empty, etc.)."""
        condition = condition.strip()

        # Check "not empty" / "empty" against a variable reference
        if condition.endswith("not empty"):
            var_part = condition[: -len("not empty")].strip()
            value = context.get(var_part, var_part)
            if isinstance(value, dict):
                value = value.get("output", value)
            return bool(value)
        if condition.endswith("empty"):
            var_part = condition[: -len("empty")].strip()
            value = context.get(var_part, var_part)
            if isinstance(value, dict):
                value = value.get("output", value)
            return not bool(value)

        # Try comparison operators
        for op in ["!=", ">=", "<=", "==", ">", "<"]:
            if op in condition:
                parts = condition.split(op, 1)
                if len(parts) == 2:
                    left = parts[0].strip().strip("'\"")
                    right = parts[1].strip().strip("'\"")

                    # Try numeric comparison
                    try:
                        left_num = float(left)
                        right_num = float(right)
                        if op == "==":
                            return left_num == right_num
                        elif op == "!=":
                            return left_num != right_num
                        elif op == ">":
                            return left_num > right_num
                        elif op == "<":
                            return left_num < right_num
                        elif op == ">=":
                            return left_num >= right_num
                        elif op == "<=":
                            return left_num <= right_num
                    except ValueError:
                        pass

                    # String comparison (case-insensitive for booleans)
                    left_cmp = left.lower()
                    right_cmp = right.lower()
                    if op == "==":
                        return left_cmp == right_cmp
                    elif op == "!=":
                        return left_cmp != right_cmp
                    elif op == ">":
                        return left > right
                    elif op == "<":
                        return left < right
                    elif op == ">=":
                        return left >= right
                    elif op == "<=":
                        return left <= right

        # "contains"
        if " contains " in condition:
            parts = condition.split(" contains ", 1)
            return parts[1].strip().strip("'\"") in parts[0].strip().strip("'\"")

        # Default: truthy check
        return bool(condition)
