"""Human-in-the-loop approval gates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt


@dataclass
class ApprovalResult:
    approved: bool
    edited_output: str | None = None
    reason: str | None = None


class ApprovalManager:

    def __init__(self, mode: str = "cli"):
        self.mode = mode
        self.console = Console()
        self.pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, ApprovalResult] = {}

    async def request_approval(
        self,
        step_id: str,
        agent_name: str,
        task: str,
        output: str,
    ) -> ApprovalResult:
        if self.mode == "dashboard":
            return await self._request_dashboard_approval(step_id, agent_name, task, output)
        return await self._request_cli_approval(step_id, agent_name, task, output)

    async def _request_cli_approval(
        self, step_id: str, agent_name: str, task: str, output: str
    ) -> ApprovalResult:
        """CLI-based approval: show panel and prompt."""
        # Truncate output for display
        display_output = output[:500] + "..." if len(output) > 500 else output

        panel = Panel(
            f"[bold]Step:[/bold] {step_id}\n"
            f"[bold]Agent:[/bold] {agent_name}\n"
            f"[bold]Task:[/bold] {task}\n\n"
            f"[bold]Output:[/bold]\n{display_output}",
            title="🔔 Approval Required",
            border_style="yellow",
        )
        self.console.print(panel)

        choice = Prompt.ask(
            "[bold yellow]Action[/bold yellow]",
            choices=["a", "r", "e"],
            default="a",
        )

        if choice == "a":
            self.console.print("[green]✅ Approved[/green]")
            return ApprovalResult(approved=True)
        elif choice == "r":
            reason = await asyncio.to_thread(
                Prompt.ask, "[red]Rejection reason[/red]", default="No reason given"
            )
            self.console.print(f"[red]❌ Rejected: {reason}[/red]")
            return ApprovalResult(approved=False, reason=reason)
        else:  # edit
            self.console.print("[blue]✏️  Edit mode — enter new output (end with empty line):[/blue]")
            lines = []
            while True:
                line = await asyncio.to_thread(input)
                if line == "":
                    break
                lines.append(line)
            edited = "\n".join(lines) if lines else output
            self.console.print("[green]✅ Approved with edits[/green]")
            return ApprovalResult(approved=True, edited_output=edited)

    async def _request_dashboard_approval(
        self, step_id: str, agent_name: str, task: str, output: str
    ) -> ApprovalResult:
        event = asyncio.Event()
        self.pending_approvals[step_id] = event

        # Wait for the dashboard to send approval
        await event.wait()

        result = self._approval_results.pop(step_id, ApprovalResult(approved=True))
        self.pending_approvals.pop(step_id, None)
        return result

    def resolve_approval(
        self,
        step_id: str,
        approved: bool,
        edited_output: str | None = None,
        reason: str | None = None,
    ):
        self._approval_results[step_id] = ApprovalResult(
            approved=approved,
            edited_output=edited_output,
            reason=reason,
        )
        event = self.pending_approvals.get(step_id)
        if event:
            event.set()
