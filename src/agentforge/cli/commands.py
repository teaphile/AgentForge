"""CLI entry points for agentforge."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentforge._version import __version__

app = typer.Typer(
    name="agentforge",
    help="AgentForge — multi-agent orchestration framework.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name"),
    template: str = typer.Option(
        "hello_world",
        help="Template: hello_world, research_writer, code_reviewer, customer_support",
    ),
):
    """Create a new AgentForge project."""
    project_dir = Path(name)

    if project_dir.exists():
        console.print(f"[red]Error:[/red] Directory '{name}' already exists.")
        raise typer.Exit(code=1)

    project_dir.mkdir(parents=True)

    # Find template
    templates_dir = Path(__file__).parent.parent / "templates"
    template_file = templates_dir / f"{template}.yaml"

    if template_file.exists():
        shutil.copy(template_file, project_dir / "agents.yaml")
    else:
        # Create a minimal default
        default_yaml = (
            'team:\n'
            f'  name: "{name}"\n'
            '  llm: "openai/gpt-4o-mini"\n'
            '\n'
            'agents:\n'
            '  assistant:\n'
            '    role: "Helpful Assistant"\n'
            '    goal: "Answer questions clearly and accurately"\n'
            '\n'
            'workflow:\n'
            '  steps:\n'
            '    - id: answer\n'
            '      agent: assistant\n'
            '      task: "{{input}}"\n'
        )
        (project_dir / "agents.yaml").write_text(default_yaml)

    # Create run.py
    run_py = (
        'from agentforge import Forge\n'
        '\n'
        'forge = Forge.from_yaml("agents.yaml")\n'
        'result = forge.run(task=input("Enter your task: "))\n'
        'print(result.output)\n'
    )
    (project_dir / "run.py").write_text(run_py)

    # Create .env.example
    env_example = (
        "# AgentForge Environment Variables\n"
        "# Uncomment and set the API keys for the providers you use.\n"
        "\n"
        "# OPENAI_API_KEY=sk-...\n"
        "# ANTHROPIC_API_KEY=sk-ant-...\n"
        "# GROQ_API_KEY=gsk_...\n"
        "# GOOGLE_API_KEY=...\n"
        "\n"
        "# For free local models, install Ollama: https://ollama.ai\n"
        "# Then use llm: ollama/llama3.2 in agents.yaml\n"
    )
    (project_dir / ".env.example").write_text(env_example)

    # Create .gitignore
    gitignore = ".agentforge/\n.env\n__pycache__/\n*.pyc\n"
    (project_dir / ".gitignore").write_text(gitignore)

    console.print(
        Panel(
            f"[bold green]✅ Project '{name}' created![/bold green]\n\n"
            f"[bold]Next steps:[/bold]\n"
            f"  cd {name}\n"
            f"  export OPENAI_API_KEY=your-key  [dim]# or use Ollama for free local models[/dim]\n"
            f"  agentforge run",
            title="⚡ AgentForge",
            border_style="green",
        )
    )


@app.command()
def run(
    yaml_path: str = typer.Option("agents.yaml", "--yaml", "-y", help="Path to agents.yaml"),
    input_text: str = typer.Option(None, "--input", "-i", help="Task input"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Preview mode — no real actions"),
    dashboard: bool = typer.Option(False, "--dashboard", help="Start live dashboard"),
    port: int = typer.Option(8420, "--port", "-p", help="Dashboard port"),
):
    """Run the workflow defined in agents.yaml."""
    from agentforge.core.forge import Forge
    from agentforge.config.loader import ConfigError
    from agentforge.observe.tracer import TraceEvent, EventType

    # Load config
    try:
        forge = Forge.from_yaml(yaml_path)
    except ConfigError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    # Get input
    if input_text is None:
        from rich.prompt import Prompt

        input_text = Prompt.ask("[bold cyan]Enter your task[/bold cyan]")

    # Print header
    team_config = forge.config.get("team", {})
    agents_list = list(forge.config.get("agents", {}).keys())
    steps_count = len(forge.config.get("workflow", {}).get("steps", []))

    console.print(f"\n[bold]⚡ AgentForge[/bold] v{__version__}")
    console.print(
        f"[dim]Team:[/dim] {team_config.get('name', 'Unknown')} "
        f"[dim]|[/dim] [dim]Agents:[/dim] {len(agents_list)} "
        f"[dim]|[/dim] [dim]Steps:[/dim] {steps_count}"
    )

    if dry_run:
        console.print("[yellow]🔍 DRY RUN MODE — tools will be simulated[/yellow]")
    if dashboard:
        console.print(f"[blue]📊 Dashboard: http://localhost:{port}[/blue]")

    console.print()

    # Set up CLI event subscriber for real-time output
    step_counter = {"current": 0}

    def on_event(event: TraceEvent):
        if event.event_type == EventType.STEP_START:
            step_counter["current"] += 1
            model = event.data.get("model", forge.llm_router.default_model)
            console.print(
                f"  [bold]▸[/bold] Step {step_counter['current']}/{steps_count}: "
                f"[cyan]{event.step_id}[/cyan] "
                f"[dim][{event.agent_name} → {model}][/dim]..."
            )
        elif event.event_type == EventType.STEP_END:
            duration = event.duration_ms / 1000 if event.duration_ms else 0
            tokens = (event.tokens.get("input", 0) + event.tokens.get("output", 0))
            cost = event.cost or 0
            status = "[green]✓[/green]" if event.data.get("success") else "[red]✗[/red]"
            console.print(
                f"    {status} Done ({duration:.1f}s, {tokens:,} tokens, ${cost:.4f})"
            )
        elif event.event_type == EventType.TOOL_CALL:
            tool_name = event.data.get("tool", "unknown")
            if event.data.get("dry_run"):
                console.print(f"    [dim]🔧 [DRY RUN] {tool_name}[/dim]")
            else:
                console.print(f"    [dim]🔧 {tool_name}[/dim]")
        elif event.event_type == EventType.ERROR:
            console.print(f"    [red]❌ Error: {event.data.get('error', 'Unknown')}[/red]")
        elif event.event_type == EventType.APPROVAL_REQUESTED:
            console.print(f"    [yellow]🔔 Approval required for step {event.step_id}[/yellow]")

    forge.event_bus.subscribe_sync(on_event)

    # Execute
    try:
        result = forge.run(input_text, dry_run=dry_run, dashboard=dashboard, port=port)
    except Exception as e:
        console.print(f"\n[red]Execution Error:[/red] {e}")
        raise typer.Exit(code=1)

    # Print final output
    if result.output:
        console.print()
        console.print(
            Panel(
                result.output,
                title="[bold]Output[/bold]",
                border_style="green" if result.success else "red",
                expand=True,
            )
        )

    # Print cost summary
    if result.cost.total_cost > 0 or result.cost.total_tokens.total > 0:
        console.print()
        table = Table(title="Cost Summary", show_header=True, header_style="bold cyan")
        table.add_column("Agent", style="white")
        table.add_column("Model", style="dim")
        table.add_column("Tokens", justify="right", style="yellow")
        table.add_column("Cost", justify="right", style="green")

        for step_result in result.steps:
            tokens = step_result.tokens.total
            table.add_row(
                step_result.agent_name,
                step_result.model_used or "—",
                f"{tokens:,}",
                f"${step_result.cost:.4f}",
            )

        table.add_section()
        table.add_row(
            "[bold]Total[/bold]",
            "",
            f"[bold]{result.cost.total_tokens.total:,}[/bold]",
            f"[bold]${result.cost.total_cost:.4f}[/bold]",
        )
        console.print(table)

    # Print duration
    console.print(f"\n[dim]⏱️  Completed in {result.duration:.1f} seconds[/dim]")

    if not result.success:
        console.print(f"\n[red]Workflow completed with errors: {result.error or 'See step details'}[/red]")
        raise typer.Exit(code=1)


@app.command()
def validate(
    yaml_path: str = typer.Option("agents.yaml", "--yaml", "-y"),
):
    """Validate agents.yaml without executing."""
    from agentforge.config.loader import ConfigError, ConfigLoader

    try:
        config = ConfigLoader.load(yaml_path)
    except ConfigError as e:
        console.print(f"[red]❌ Validation failed:[/red]\n{e}")
        raise typer.Exit(code=1)

    team_config = config.get("team", {})
    agents_config = config.get("agents", {})
    workflow_config = config.get("workflow", {})

    # Additional checks
    errors = []
    agent_names = set(agents_config.keys())

    # Check agent references in workflow steps
    for step_item in workflow_config.get("steps", []):
        if isinstance(step_item, dict):
            if "parallel" in step_item:
                for s in step_item["parallel"]:
                    agent = s.get("agent", "")
                    if agent and agent not in agent_names:
                        errors.append(f"Agent '{agent}' referenced in parallel step but not defined")
            else:
                agent = step_item.get("agent", "")
                step_id = step_item.get("id", "?")
                if agent and agent not in agent_names:
                    errors.append(f"Agent '{agent}' referenced in step '{step_id}' but not defined")

    # Check LLM format
    team_llm = team_config.get("llm", "")
    if team_llm and "/" not in team_llm:
        errors.append(f"Team LLM '{team_llm}' should be in 'provider/model' format")

    for name, agent_conf in agents_config.items():
        agent_llm = agent_conf.get("llm")
        if agent_llm and "/" not in agent_llm:
            errors.append(f"Agent '{name}' LLM '{agent_llm}' should be in 'provider/model' format")

    if errors:
        console.print("[red]❌ Validation failed:[/red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)

    # Success
    console.print("[green]✅ agents.yaml is valid![/green]")
    console.print(f"  Team: {team_config.get('name', 'Unknown')}")
    agent_list = ", ".join(f"{n} ({c.get('role', '?')})" for n, c in agents_config.items())
    console.print(f"  Agents: {agent_list}")
    console.print(f"  Steps: {len(workflow_config.get('steps', []))}")

    # List tools
    all_tools = set()
    for agent_conf in agents_config.values():
        for t in agent_conf.get("tools", []):
            all_tools.add(t)
    if all_tools:
        console.print(f"  Tools: {', '.join(sorted(all_tools))}")


@app.command(name="dashboard")
def dashboard_cmd(
    port: int = typer.Option(8420, "--port", "-p"),
):
    """Start the dashboard server standalone."""
    import uvicorn

    from agentforge.dashboard.app import create_dashboard_app
    from agentforge.observe.events import EventBus
    from agentforge.observe.tracer import Tracer

    console.print(f"[bold]⚡ AgentForge Dashboard[/bold] — http://localhost:{port}")

    app = create_dashboard_app(
        event_bus=EventBus(),
        tracer=Tracer(),
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


@app.command()
def cost(
    yaml_path: str = typer.Option("agents.yaml", "--yaml", "-y"),
    input_text: str = typer.Option("ping", "--input", "-i", help="Dummy task for cost estimation"),
):
    """Show cost estimate by performing a dry run."""
    from agentforge.core.forge import Forge
    from agentforge.config.loader import ConfigError

    try:
        forge = Forge.from_yaml(yaml_path)
    except ConfigError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(code=1)

    result = forge.run(task=input_text, dry_run=True)

    table = Table(title="Cost Estimate (Dry Run)", show_header=True, header_style="bold cyan")
    table.add_column("Step", style="white")
    table.add_column("Agent", style="dim")
    table.add_column("Model", style="dim")
    table.add_column("Tokens", justify="right", style="yellow")
    table.add_column("Cost", justify="right", style="green")

    for sr in result.steps:
        table.add_row(
            sr.step_id,
            sr.agent_name,
            sr.model_used or "—",
            f"{sr.tokens.total:,}" if sr.tokens else "0",
            f"${sr.cost:.4f}" if sr.cost else "$0.0000",
        )

    table.add_section()
    table.add_row(
        "[bold]Total[/bold]", "", "",
        f"[bold]{result.cost.total_tokens.total:,}[/bold]",
        f"[bold]${result.cost.total_cost:.4f}[/bold]",
    )
    console.print(table)
    console.print(f"\n[dim]Duration: {result.duration:.1f}s (dry run)[/dim]")


@app.command()
def version():
    """Show AgentForge version."""
    console.print(f"⚡ AgentForge v{__version__}")


if __name__ == "__main__":
    app()
