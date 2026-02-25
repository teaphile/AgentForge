#!/usr/bin/env python3
"""
Live demo of AgentForge — runs a full multi-agent workflow
with a mock LLM (no API key needed).
"""
import asyncio
from unittest.mock import AsyncMock, patch

from agentforge.core.forge import Forge

# ──── Mock LLM responses per agent ────
MOCK_RESPONSES = {
    "researcher": (
        "## Research Findings: AI in 2026\n\n"
        "1. **Agentic AI** is the dominant theme — autonomous systems that plan, "
        "reason, and execute multi-step tasks are now mainstream.\n\n"
        "2. **Multi-modal models** (text + image + audio + video) are standard. "
        "GPT-5, Claude 4, and Gemini Ultra 2 all support native multi-modal I/O.\n\n"
        "3. **Edge AI** has exploded — models running on-device (phones, laptops) "
        "with <1B parameters can now rival GPT-3.5 quality.\n\n"
        "4. **AI regulation** is active in 47 countries. The EU AI Act is fully "
        "enforced, requiring transparency for high-risk systems.\n\n"
        "5. **Open-source models** (Llama 4, Mistral Large 3) match proprietary "
        "models on most benchmarks, democratizing access.\n\n"
        "Sources: Nature AI Review (2026), MIT Technology Review, arXiv papers."
    ),
    "writer": (
        "# The State of AI in 2026: A New Era of Intelligence\n\n"
        "Artificial intelligence has reached an inflection point. What was once "
        "a research curiosity is now the backbone of modern software.\n\n"
        "## Agentic AI Takes Center Stage\n\n"
        "The biggest shift in 2026 is the rise of *agentic AI* — systems that "
        "don't just answer questions, but autonomously plan and execute complex "
        "multi-step workflows. Frameworks like AgentForge make it possible to "
        "orchestrate teams of AI agents with a simple YAML file.\n\n"
        "## Multi-Modal is the New Normal\n\n"
        "GPT-5, Claude 4, and Gemini Ultra 2 all support native multi-modal "
        "input and output. You can hand these models a video and get back a "
        "structured report. The era of text-only AI is firmly behind us.\n\n"
        "## AI at the Edge\n\n"
        "Perhaps the most democratizing trend is edge AI. Models with less than "
        "one billion parameters, running entirely on your phone, now rival what "
        "GPT-3.5 could do in 2023. Privacy-first, latency-free intelligence.\n\n"
        "## The Regulatory Landscape\n\n"
        "With 47 countries now actively regulating AI, transparency and safety "
        "are no longer optional. The EU AI Act requires clear disclosure when "
        "high-risk decisions are made by AI systems.\n\n"
        "## Open Source Wins\n\n"
        "Llama 4 and Mistral Large 3 match proprietary models on nearly every "
        "benchmark. The open-source community has ensured that cutting-edge AI "
        "isn't locked behind corporate walls.\n\n"
        "---\n\n"
        "*The future of AI isn't just smarter models — it's smarter systems. "
        "Teams of agents, working together, tackling problems no single model "
        "could solve alone.*"
    ),
}

call_count = {"n": 0}
agent_order = ["researcher", "writer"]


async def mock_complete(**kwargs):
    """Fake LLM that returns pre-written responses."""
    current_model = kwargs.get("model", "openai/gpt-4o-mini")
    idx = min(call_count["n"], len(agent_order) - 1)
    agent = agent_order[idx]
    call_count["n"] += 1

    # Simulate a realistic response structure
    class FakeChoice:
        class FakeMessage:
            content = MOCK_RESPONSES[agent]
            tool_calls = None
        message = FakeMessage()

    class FakeUsage:
        prompt_tokens = 350
        completion_tokens = 420
        total_tokens = 770

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()
        model = current_model
        _hidden_params = {"response_cost": 0.0012}

    return FakeResponse()


def main():
    print("=" * 60)
    print("  ⚡ AgentForge — Live Demo (Mock LLM, no API key)")
    print("=" * 60)
    print()

    # Load the research+writer example config
    forge = Forge.from_yaml("examples/02_research_writer/agents.yaml")

    # Subscribe to events so we can see real-time progress
    from agentforge.observe.tracer import TraceEvent, EventType
    from rich.console import Console
    console = Console()

    def on_event(event: TraceEvent):
        if event.event_type == EventType.STEP_START:
            console.print(
                f"  [bold]▸[/bold] Running step [cyan]{event.step_id}[/cyan] "
                f"[dim]({event.agent_name})[/dim]..."
            )
        elif event.event_type == EventType.STEP_END:
            ms = event.duration_ms or 0
            console.print(f"    [green]✓[/green] Done ({ms/1000:.1f}s)")
        elif event.event_type == EventType.WORKFLOW_START:
            team = event.data.get("team", "")
            agents = event.data.get("agents", [])
            console.print(f"  Team: [bold]{team}[/bold]")
            console.print(f"  Agents: {', '.join(agents)}")
            console.print()
        elif event.event_type == EventType.WORKFLOW_END:
            pass

    forge.event_bus.subscribe_sync(on_event)

    # Patch LLM calls with our mock
    with patch("agentforge.llm.router.acompletion", new=mock_complete), \
         patch("agentforge.llm.router.litellm") as mock_litellm:
        mock_litellm.suppress_debug_info = True
        mock_litellm.completion_cost.return_value = 0.0012
        result = forge.run("Latest trends in AI for 2026")

    # Show results
    print()
    console.print("[bold]━━━ FINAL OUTPUT ━━━[/bold]")
    print()
    print(result.output)
    print()

    # Show stats
    console.print("[bold]━━━ RUN STATS ━━━[/bold]")
    console.print(f"  Success:  [green]{result.success}[/green]")
    console.print(f"  Duration: {result.duration:.2f}s")
    console.print(f"  Steps:    {len(result.steps)}")
    console.print(f"  Cost:     ${result.cost.total_cost:.4f}")
    console.print(f"  Tokens:   {result.cost.total_tokens.total:,}")
    print()


if __name__ == "__main__":
    main()
