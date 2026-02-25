"""Main orchestrator tying agents, workflows, tools, and observability together."""

from __future__ import annotations

import asyncio
import time
import threading
import webbrowser
from pathlib import Path
from typing import Union

from agentforge.config.loader import ConfigLoader
from agentforge.control.approval import ApprovalManager
from agentforge.control.dry_run import DryRunController
from agentforge.core.result import CostSummary, ForgeResult, TokenUsage
from agentforge.core.team import Team
from agentforge.core.workflow import Workflow
from agentforge.llm.router import LLMRouter
from agentforge.observe.events import EventBus
from agentforge.observe.tracer import EventType, TraceEvent, Tracer


class Forge:
    """
    Usage::

        forge = Forge.from_yaml("agents.yaml")
        result = forge.run("Write a blog post about Python patterns")
    """

    def __init__(self, team: Team, workflow: Workflow, config: dict | None = None):
        self.team = team
        self.workflow = workflow
        self.config = config or {}
        self.tracer = Tracer()
        self.event_bus = EventBus()

        team_config = self.config.get("team", {})
        observe_config = team_config.get("observe", {})

        self.llm_router = LLMRouter(
            default_model=team_config.get("llm", "openai/gpt-4o-mini"),
            cost_tracking=observe_config.get("cost_tracking", True),
        )
        self.dry_run_controller = DryRunController()
        self.approval_manager = ApprovalManager()

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Forge":
        config = ConfigLoader.load(path)
        team = Team.from_config(config)
        workflow = Workflow.from_config(config, team)
        return cls(team=team, workflow=workflow, config=config)

    @classmethod
    def from_dict(cls, config: dict) -> "Forge":
        config = ConfigLoader.validate(config)
        team = Team.from_config(config)
        workflow = Workflow.from_config(config, team)
        return cls(team=team, workflow=workflow, config=config)

    def run(
        self,
        task: str,
        *,
        dry_run: bool | None = None,
        dashboard: bool = False,
        port: int = 8420,
    ) -> ForgeResult:
        """Synchronous entry point. Wraps the async `arun()` method."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.arun(task, dry_run=dry_run, dashboard=dashboard, port=port),
                )
                return future.result()
        else:
            return asyncio.run(self.arun(task, dry_run=dry_run, dashboard=dashboard, port=port))

    async def arun(
        self,
        task: str,
        *,
        dry_run: bool | None = None,
        dashboard: bool = False,
        port: int = 8420,
    ) -> ForgeResult:
        """Async entry point — use this when already in an async context."""
        # Determine dry_run mode
        if dry_run is None:
            dry_run = self.config.get("team", {}).get("control", {}).get("dry_run", False)

        # Dashboard mode
        if dashboard:
            self._start_dashboard(port)

        # Start tracing
        self.tracer = Tracer()
        self.tracer.start()

        self.tracer.record(
            TraceEvent(
                event_type=EventType.WORKFLOW_START,
                data={
                    "team": self.team.name,
                    "agents": self.team.list_agents(),
                    "step_count": len(self.workflow.steps),
                    "dry_run": dry_run,
                },
            )
        )
        await self.event_bus.emit(
            TraceEvent(
                event_type=EventType.WORKFLOW_START,
                data={
                    "team": self.team.name,
                    "agents": self.team.list_agents(),
                    "step_count": len(self.workflow.steps),
                },
            )
        )

        # Execute workflow
        start_time = time.time()
        try:
            step_results = await self.workflow.execute(
                user_input=task,
                tracer=self.tracer,
                event_bus=self.event_bus,
                llm_router=self.llm_router,
                approval_manager=self.approval_manager,
                dry_run=dry_run,
            )
        except Exception as e:
            duration = time.time() - start_time
            self.tracer.record(
                TraceEvent(
                    event_type=EventType.ERROR,
                    data={"error": str(e)},
                )
            )
            self.tracer.record(
                TraceEvent(
                    event_type=EventType.WORKFLOW_END,
                    data={"success": False, "error": str(e)},
                    duration_ms=duration * 1000,
                )
            )
            return ForgeResult(
                output="",
                steps=[],
                trace=self.tracer.get_timeline(),
                cost=CostSummary(),
                duration=duration,
                success=False,
                error=str(e),
            )

        duration = time.time() - start_time

        # Build cost summary
        cost_breakdown = self.tracer.get_cost_breakdown()
        cost_summary = CostSummary(
            total_cost=cost_breakdown["total_cost"],
            total_tokens=TokenUsage(
                input_tokens=cost_breakdown["total_tokens"]["input"],
                output_tokens=cost_breakdown["total_tokens"]["output"],
            ),
            by_agent=cost_breakdown["by_agent"],
            by_model=cost_breakdown["by_model"],
            by_step=cost_breakdown["by_step"],
        )

        # Determine final output (last step's output)
        final_output = ""
        if step_results:
            final_output = step_results[-1].output

        success = all(sr.success for sr in step_results)

        self.tracer.record(
            TraceEvent(
                event_type=EventType.WORKFLOW_END,
                data={"success": success, "total_cost": cost_summary.total_cost},
                duration_ms=duration * 1000,
            )
        )
        await self.event_bus.emit(
            TraceEvent(
                event_type=EventType.WORKFLOW_END,
                data={"success": success, "total_cost": cost_summary.total_cost},
                duration_ms=duration * 1000,
            )
        )

        return ForgeResult(
            output=final_output,
            steps=step_results,
            trace=self.tracer.get_timeline(),
            cost=cost_summary,
            duration=duration,
            success=success,
        )

    def _start_dashboard(self, port: int):
        """Start the dashboard server in a background thread."""

        def _run_server():
            from agentforge.dashboard.app import create_dashboard_app
            import uvicorn

            app = create_dashboard_app(
                event_bus=self.event_bus,
                tracer=self.tracer,
                approval_manager=self.approval_manager,
            )
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()

        time.sleep(0.5)

        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
