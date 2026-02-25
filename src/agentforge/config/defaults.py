"""Default configuration values."""

from __future__ import annotations

import copy

DEFAULTS = {
    "team": {
        "name": "AgentForge Team",
        "description": "",
        "llm": "openai/gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 4096,
        "memory": {
            "enabled": True,
            "backend": "sqlite",
            "path": ".agentforge/memory.db",
            "shared": True,
        },
        "observe": {
            "trace": True,
            "cost_tracking": True,
            "log_level": "info",
            "log_format": "pretty",
        },
        "control": {
            "dry_run": False,
            "max_retries": 3,
            "timeout": 300,
            "confidence_threshold": 0.4,
        },
    },
    "agent_defaults": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "backstory": "",
        "instructions": "",
        "tools": [],
        "fallback": [],
        "memory": {
            "enabled": True,
            "type": "short_term",
            "recall_limit": 10,
        },
        "control": {
            "require_approval": False,
            "max_iterations": 10,
            "allowed_actions": [],
            "blocked_actions": [],
        },
    },
}


def merge_with_defaults(config: dict) -> dict:
    return _deep_merge(copy.deepcopy(DEFAULTS), config)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Returns a new dict."""
    merged = {}
    for key in set(base) | set(override):
        if key in base and key in override:
            bv, ov = base[key], override[key]
            if isinstance(bv, dict) and isinstance(ov, dict):
                merged[key] = _deep_merge(bv, ov)
            else:
                merged[key] = copy.deepcopy(ov)
        elif key in override:
            merged[key] = copy.deepcopy(override[key])
        else:
            merged[key] = copy.deepcopy(base[key])
    return merged
