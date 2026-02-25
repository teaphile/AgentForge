"""Tests for the Tracer and EventBus."""

from __future__ import annotations

import pytest

from agentforge.observe.tracer import Tracer, TraceEvent, EventType
from agentforge.observe.export import export_trace_json, export_trace_dict
from agentforge.observe.cost_report import generate_cost_dict


class TestEventType:
    def test_event_types_exist(self):
        assert EventType.STEP_START is not None
        assert EventType.STEP_END is not None
        assert EventType.TOOL_CALL is not None
        assert EventType.AGENT_THINKING is not None
        assert EventType.AGENT_RESPONSE is not None


class TestTraceEvent:
    def test_create_event(self):
        event = TraceEvent(
            event_type=EventType.STEP_START,
            step_id="s1",
            agent_name="writer",
            data={"task": "Write something"},
        )
        assert event.event_type == EventType.STEP_START
        assert event.step_id == "s1"
        assert event.agent_name == "writer"

    def test_to_dict(self):
        event = TraceEvent(
            event_type=EventType.STEP_START,
            step_id="s1",
            agent_name="writer",
        )
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["event_type"] == "step_start"


class TestTracer:
    def test_init(self):
        tracer = Tracer()
        assert len(tracer.events) == 0

    def test_record_event(self, tracer):
        event = TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="writer")
        tracer.record(event)
        assert len(tracer.events) == 1

    def test_multiple_events(self, tracer):
        tracer.record(TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="writer"))
        tracer.record(TraceEvent(
            event_type=EventType.AGENT_THINKING,
            step_id="s1", agent_name="writer",
            data={"model": "gpt-4o"},
        ))
        tracer.record(TraceEvent(event_type=EventType.STEP_END, step_id="s1", agent_name="writer"))
        assert len(tracer.events) == 3

    def test_get_timeline(self, tracer):
        tracer.record(TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="a"))
        timeline = tracer.get_timeline()
        assert len(timeline) == 1
        assert isinstance(timeline[0], dict)

    def test_start_and_elapsed(self, tracer):
        tracer.start()
        assert tracer.start_time > 0
        elapsed = tracer.elapsed()
        assert elapsed >= 0

    def test_get_cost_breakdown(self, tracer):
        breakdown = tracer.get_cost_breakdown()
        assert isinstance(breakdown, dict)
        assert "total_cost" in breakdown


class TestEventBus:
    def test_subscribe_sync(self, event_bus):
        received = []
        event_bus.subscribe_sync(lambda event: received.append(event))
        # emit is async, so we test subscribe_sync works
        assert len(event_bus._sync_subscribers) == 1

    @pytest.mark.asyncio
    async def test_emit_to_sync_subscriber(self, event_bus):
        received = []
        event_bus.subscribe_sync(lambda event: received.append(event))
        event = TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="a")
        await event_bus.emit(event)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_emit_to_async_subscriber(self, event_bus):
        received = []
        async def handler(event):
            received.append(event)
        event_bus.subscribe(handler)
        event = TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="a")
        await event_bus.emit(event)
        assert len(received) == 1

    def test_clear(self, event_bus):
        event_bus.subscribe_sync(lambda e: None)
        event_bus.clear()
        assert len(event_bus._sync_subscribers) == 0
        assert len(event_bus._subscribers) == 0


class TestExport:
    def test_export_dict(self, tracer):
        tracer.record(TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="a"))
        data = export_trace_dict(tracer)
        assert isinstance(data, dict) or isinstance(data, list)

    def test_export_json_file(self, tracer, tmp_path):
        tracer.record(TraceEvent(event_type=EventType.STEP_START, step_id="s1", agent_name="a"))
        out = tmp_path / "trace.json"
        export_trace_json(tracer, str(out))
        assert out.exists()
        content = out.read_text()
        assert "s1" in content


class TestCostReport:
    def test_generate_cost_dict(self, tracer):
        tracer.record(TraceEvent(
            event_type=EventType.AGENT_RESPONSE,
            step_id="s1",
            agent_name="a",
            data={"model": "gpt-4o"},
            cost=0.05,
            tokens={"input": 1000, "output": 500},
        ))
        data = generate_cost_dict(tracer)
        assert isinstance(data, dict)
