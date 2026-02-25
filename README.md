<div align="center">

# ⚡ AgentForge

**Build AI agent teams with YAML. No boilerplate.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-156%20passed-brightgreen.svg)]()
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

</div>

---

## What is AgentForge?

AgentForge is a Python framework that lets you build multi-agent AI systems using just YAML configuration. Instead of writing hundreds of lines of orchestration code, you define your agents, give them roles and tools, wire up a workflow, and let the framework handle the rest.

Think of it like this — you describe *what* your agents should do, and AgentForge figures out *how* to run them.

```yaml
# That's it. Two agents, one pipeline, zero boilerplate.
agents:
  researcher:
    role: Research Analyst
    goal: Find accurate information
    tools: [web_search]

  writer:
    role: Content Writer
    goal: Write clear articles

workflow:
  steps:
    - id: research
      agent: researcher
      task: "Research: {{input}}"
      save_as: findings

    - id: write
      agent: writer
      task: "Write an article using: {{findings}}"
```

```python
from agentforge import Forge

forge = Forge.from_yaml("agents.yaml")
result = forge.run(task="Latest breakthroughs in quantum computing")
print(result.output)
```

That's a working multi-agent pipeline. Two agents collaborating, with the researcher's output automatically flowing into the writer's task.

---

## Why AgentForge?

Most agent frameworks make you write a lot of Python glue code just to get two agents talking to each other. AgentForge takes a different approach:

- **YAML-first** — Your entire agent system lives in one readable config file. Change behavior without touching code.
- **Works with 100+ models** — OpenAI, Anthropic, Ollama (free local models), Groq, Gemini, and more. Switch models by changing one line.
- **Production-ready defaults** — Timeout enforcement, cost tracking, memory, retries, and guardrails are built in, not afterthoughts.
- **Actually tested** — 156 tests covering security, concurrency, workflow execution, and edge cases.

---

## Getting Started

### Installation

```bash
pip install agentforge
```

### Create your first project

The fastest way to start:

```bash
agentforge init my_project
cd my_project
```

This creates a ready-to-run project with `agents.yaml`, `run.py`, and example configuration. Four templates are included:

| Template | What it does |
|----------|-------------|
| `hello_world` | Single agent, simplest possible setup (default) |
| `research_writer` | Two-agent research → writing pipeline |
| `code_reviewer` | Multi-step code analysis workflow |
| `customer_support` | Conditional routing based on query type |

```bash
# Use a specific template
agentforge init my_project --template research_writer
```

### Set up your API key

```bash
export OPENAI_API_KEY=sk-...

# Or use free local models with Ollama (no API key needed)
# Just change the llm line in agents.yaml to: ollama/llama3.2
```

### Run it

```bash
agentforge run --input "Write a blog post about Python design patterns"
```

Or from Python:

```python
from agentforge import Forge

forge = Forge.from_yaml("agents.yaml")
result = forge.run(task="Write a blog post about Python design patterns")

print(result.output)           # The final text
print(result.cost.total_cost)  # How much it cost
print(result.duration)         # How long it took
```

Need async? Use `arun()`:

```python
result = await forge.arun(task="Your task here")
```

---

## Features

### Workflow Engine

AgentForge supports multiple execution patterns — you can mix and match them in the same workflow:

**Sequential** — steps run one after another, each can use the output of previous steps:

```yaml
workflow:
  steps:
    - id: research
      agent: researcher
      task: "Research {{input}}"
      save_as: data

    - id: write
      agent: writer
      task: "Write about {{data}}"
```

**Parallel** — run multiple agents at the same time:

```yaml
workflow:
  steps:
    - parallel:
        - id: search_news
          agent: news_agent
          task: "Find recent news about {{input}}"
          save_as: news

        - id: search_papers
          agent: academic_agent
          task: "Find research papers about {{input}}"
          save_as: papers

    - id: synthesize
      agent: writer
      task: "Combine {{news}} and {{papers}} into a report"
```

**Conditional** — skip steps based on conditions:

```yaml
- id: deep_dive
  agent: researcher
  task: "Do detailed analysis of {{data}}"
  condition: "data not empty"
```

**Branching** — route to different steps on success or failure:

```yaml
- id: attempt
  agent: coder
  task: "Write the code"
  on_success: review
  on_fail: fallback

- id: review
  agent: reviewer
  task: "Review the code"

- id: fallback
  agent: senior_coder
  task: "Fix the failed attempt"
```

**Looping** — retry steps or create cycles:

```yaml
- id: generate
  agent: writer
  task: "Draft content"
  retry_on_fail: 3    # Retry up to 3 times on failure
```

### Built-in Tools

Agents can use tools to interact with the outside world. Six tools come built-in:

| Tool | What it does | Security |
|------|-------------|----------|
| `web_search` | Search the web via DuckDuckGo | — |
| `file_read` | Read files from disk | Sandboxed to configured directory |
| `file_write` | Write files to disk | Sandboxed to configured directory |
| `http_request` | Make HTTP GET/POST requests | SSRF protection (blocks private IPs, cloud metadata) |
| `python_exec` | Execute Python code | Runs in isolated subprocess with import allowlist |
| `calculator` | Evaluate math expressions | AST-based parser (no eval/exec) |

Use them in your agents:

```yaml
agents:
  assistant:
    role: Research Assistant
    goal: Help with research tasks
    tools:
      - web_search
      - calculator
      - file_write
```

**Custom tools:** You can also load your own:

```yaml
tools:
  - "custom:my_module.my_tool_function"
```

### Memory

Agents can remember things across conversations:

**Short-term memory** (default) — in-process, fast, cleared when the program exits:

```yaml
agents:
  assistant:
    memory:
      type: short_term
```

**Long-term memory** — persisted to SQLite, survives restarts:

```yaml
team:
  memory:
    enabled: true
    backend: sqlite
    path: .agentforge/memory.db
    shared: true    # All agents share the same memory store
```

Agents automatically store task summaries and recall relevant context for new tasks.

### Human-in-the-Loop

Add approval gates to any step. The workflow pauses and waits for human approval before continuing:

```yaml
- id: publish
  agent: writer
  task: "Write the final press release"
  approval_gate: true    # Workflow pauses here for human review
```

When running via the dashboard, approvals show up in the UI. When running via CLI, you get a prompt in the terminal.

### Cost Tracking

Every API call is tracked. You get per-step, per-agent, and per-model cost breakdowns:

```python
result = forge.run(task="...")

print(result.cost.total_cost)       # Total spend
print(result.cost.total_tokens)     # Total tokens used
print(result.cost.by_agent)         # Breakdown by agent
print(result.cost.by_model)         # Breakdown by model
```

Want to estimate costs before running? Use dry-run:

```bash
agentforge cost --yaml agents.yaml
```

### Dashboard

A real-time web UI for monitoring your agents:

```bash
agentforge dashboard
```

The dashboard shows:
- Live agent status and execution timeline
- Token usage and cost per step
- Approval management (approve/reject/edit from the browser)
- WebSocket-powered live updates

### Dry Run Mode

Preview what your agents *would* do without actually calling any APIs or tools:

```bash
agentforge run --input "Your task" --dry-run
```

```python
result = forge.run(task="Your task", dry_run=True)
```

### Timeout Enforcement

Set per-step timeouts so no single agent can block your pipeline forever:

```yaml
- id: research
  agent: researcher
  task: "Research this topic"
  timeout: 60    # Kill after 60 seconds
```

There's also a global timeout in team config:

```yaml
team:
  control:
    timeout: 300    # 5 minute max for any step
```

### Confidence Scoring

AgentForge includes a heuristic confidence checker. If an agent's answer scores below the threshold, it automatically asks the LLM to try again with a better response:

```yaml
agents:
  analyst:
    role: Data Analyst
    goal: Provide accurate analysis
    control:
      confidence_threshold: 0.5    # Re-prompt if confidence < 50%
      max_iterations: 10
```

### Output Format Hints

Tell a step to respond in a specific format:

```yaml
- id: extract
  agent: analyst
  task: "Extract key metrics from {{data}}"
  output_format: json    # Adds format instruction to the prompt
```

Supported: `text` (default), `json`, `markdown`.

### LLM Fallback Chains

If one model fails (rate limit, downtime, etc.), AgentForge automatically tries the next one:

```yaml
team:
  llm: openai/gpt-4o
  fallback_models:
    - anthropic/claude-3-haiku
    - ollama/llama3          # Free local fallback
```

Individual agents can override the team default:

```yaml
agents:
  premium_agent:
    llm: openai/gpt-4o       # Uses the expensive model
  budget_agent:
    llm: ollama/llama3.2      # Uses the free local model
```

### Guardrails

Control which tools each agent is allowed (or blocked from) using:

```yaml
agents:
  safe_agent:
    control:
      allowed_actions: [web_search, calculator]    # Only these tools
      blocked_actions: [file_write, python_exec]   # Never these tools
```

---

## CLI Reference

```bash
agentforge init <name>              # Create a new project
agentforge run                      # Run workflow (interactive prompt)
agentforge run -i "task" -y config  # Run with input and custom config
agentforge run --dry-run            # Preview without executing
agentforge run --dashboard          # Run with live dashboard
agentforge validate                 # Check YAML validity
agentforge dashboard                # Launch dashboard standalone
agentforge cost                     # Estimate cost via dry run
agentforge version                  # Show version
```

---

## Full Configuration Reference

<details>
<summary><b>Click to expand complete YAML schema</b></summary>

```yaml
team:
  name: "Team Name"
  llm: openai/gpt-4o-mini           # provider/model format
  fallback_models:
    - anthropic/claude-3-haiku
    - ollama/llama3
  temperature: 0.7                    # 0.0 = deterministic, 1.0 = creative
  max_tokens: 4096
  memory:
    enabled: true
    backend: sqlite                   # sqlite
    path: .agentforge/memory.db
    shared: true                      # Agents share memory
  observe:
    trace: true
    cost_tracking: true
    log_level: info                   # debug | info | warning | error
    log_format: pretty                # pretty | json
  control:
    dry_run: false
    max_retries: 3
    timeout: 300                      # Global step timeout (seconds)
    confidence_threshold: 0.4

agents:
  agent_name:
    role: "What this agent is"
    goal: "What it's trying to achieve"
    backstory: "Optional context"
    instructions: "Optional extra instructions"
    llm: openai/gpt-4o               # Override team model
    temperature: 0.5
    max_tokens: 2048
    fallback:
      - anthropic/claude-3-haiku
    tools:
      - web_search
      - calculator
      - "custom:module.function"
    memory:
      enabled: true
      type: short_term                # short_term | long_term
      recall_limit: 10
    control:
      max_iterations: 10
      confidence_threshold: 0.5
      allowed_actions: []
      blocked_actions: []

workflow:
  steps:
    - id: step_name
      agent: agent_name
      task: "Task with {{variable}} interpolation"
      output_format: text             # text | json | markdown
      timeout: 60
      retry_on_fail: 2
      approval_gate: false
      dry_run: false
      condition: "variable not empty"
      save_as: output_variable
      on_success: next_step_id
      on_fail: error_step_id
      next: loop_back_step_id

    - parallel:
        - id: parallel_a
          agent: agent_a
          task: "Parallel task A"
        - id: parallel_b
          agent: agent_b
          task: "Parallel task B"
```

</details>

---

## Project Structure

```
src/agentforge/
├── cli/            # CLI commands (init, run, validate, dashboard, cost)
├── config/         # YAML loading, Pydantic validation, defaults
├── control/        # Approval gates, confidence scoring, dry-run, guardrails
├── core/           # Forge orchestrator, Agent (ReAct loop), Workflow engine, Team
├── dashboard/      # FastAPI app, WebSocket manager, REST routes, static UI
├── llm/            # LiteLLM provider wrapper, router with fallback chains
├── memory/         # Short-term (in-process) and long-term (SQLite) memory
├── observe/        # Tracer, event bus, trace timeline
├── templates/      # Project scaffolding templates (4 included)
└── tools/          # Tool base class, registry, built-in tools

tests/              # 156 tests (unit + integration + security)
```

---

## Development

```bash
# Clone and install
git clone https://github.com/whoisaum/new.git
cd new
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=agentforge

# Lint
ruff check src/ tests/
```

### Tech Stack

- **Python 3.10+** — async/await throughout
- **LiteLLM** — unified interface to 100+ LLM providers
- **Pydantic v2** — config validation with typed models
- **FastAPI + Uvicorn** — dashboard server
- **Typer + Rich** — CLI with colored output
- **SQLite** — long-term memory persistence (thread-safe)
- **httpx** — async HTTP client for tools
- **pytest + pytest-asyncio** — test framework
- **ruff** — linting

---

## Supported LLM Providers

AgentForge uses [LiteLLM](https://github.com/BerriAI/litellm) under the hood, so it works with any provider LiteLLM supports. Some popular ones:

| Provider | Model format | API key env var |
|----------|-------------|-----------------|
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-3-opus` | `ANTHROPIC_API_KEY` |
| Google | `gemini/gemini-pro` | `GOOGLE_API_KEY` |
| Groq | `groq/llama3-70b` | `GROQ_API_KEY` |
| Ollama (local) | `ollama/llama3.2` | None (free) |
| Mistral | `mistral/mistral-large` | `MISTRAL_API_KEY` |

---

## Requirements

- Python 3.10 or higher
- API keys for whichever LLM provider you want to use (set as environment variables)
- Or just [install Ollama](https://ollama.ai) for free local models — no API keys needed

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built with care. If you find this useful, give it a ⭐</sub>
</div>
