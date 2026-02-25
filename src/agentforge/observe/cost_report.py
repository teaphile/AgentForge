"""Cost report generation from trace data."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from agentforge.observe.tracer import Tracer


def print_cost_report(tracer: Tracer, console: Console | None = None):
    if console is None:
        console = Console()

    breakdown = tracer.get_cost_breakdown()

    table = Table(title="Cost Summary", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="white")
    table.add_column("Model", style="dim")
    table.add_column("Tokens", justify="right", style="yellow")
    table.add_column("Cost", justify="right", style="green")

    for agent_name, info in breakdown.get("by_agent", {}).items():
        tokens = info["tokens"]["input"] + info["tokens"]["output"]
        # Find model actually used by this agent from trace events
        model = "—"
        for ev in tracer.events:
            if ev.agent_name == agent_name and ev.data.get("model"):
                model = ev.data["model"]
                break
        table.add_row(
            agent_name,
            model,
            f"{tokens:,}",
            f"${info['cost']:.4f}",
        )

    table.add_section()
    total_tokens = breakdown["total_tokens"]["input"] + breakdown["total_tokens"]["output"]
    table.add_row(
        "[bold]Total[/bold]",
        "",
        f"[bold]{total_tokens:,}[/bold]",
        f"[bold]${breakdown['total_cost']:.4f}[/bold]",
    )

    console.print(table)


def generate_cost_dict(tracer: Tracer) -> dict:
    return tracer.get_cost_breakdown()
