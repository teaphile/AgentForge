"""Trace export utilities."""

from __future__ import annotations

from pathlib import Path

from agentforge.observe.tracer import Tracer


def export_trace_json(tracer: Tracer, path: str | Path):
    tracer.export_json(str(path))


def export_trace_dict(tracer: Tracer) -> dict:
    return {
        "start_time": tracer.start_time,
        "duration": tracer.elapsed(),
        "events": tracer.get_timeline(),
        "cost_breakdown": tracer.get_cost_breakdown(),
    }
