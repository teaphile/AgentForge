# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-25

### Added
- Initial release of AgentForge
- YAML-first multi-agent orchestration
- Sequential and parallel workflow execution
- Built-in tools: web_search, file_read, file_write, http_request, calculator, python_exec
- LLM routing with fallback chains via litellm (100+ providers)
- Short-term and long-term memory (SQLite + ChromaDB)
- Human-in-the-loop approval gates
- Real-time dashboard with WebSocket streaming
- CLI with init, run, validate, dashboard, cost, and version commands
- Dry-run mode for safe previewing
- Cost tracking and reporting
- Execution tracing and JSON export
- Six example projects included
