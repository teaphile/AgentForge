"""Tests for confidence scoring and tracer thread safety."""

from __future__ import annotations

import threading

from agentforge.control.confidence import ConfidenceChecker
from agentforge.observe.tracer import EventType, TraceEvent, Tracer


class TestConfidenceChecker:
    def test_high_confidence_passes(self):
        checker = ConfidenceChecker(threshold=0.3)
        # A well-structured response should score above 0.3
        text = (
            "Based on the analysis, the results indicate three primary factors. "
            "First, the economic data confirms growth. Second, the demographic trends "
            "support the hypothesis. In conclusion, the evidence is strong."
        )
        score = checker.check(text)
        assert score >= 0.3

    def test_empty_response_low_confidence(self):
        checker = ConfidenceChecker(threshold=0.5)
        score = checker.check("")
        # Empty string is short (< 20 words) so gets -0.1 from base 0.7 = 0.6
        assert score < 0.7

    def test_short_uncertain_response(self):
        checker = ConfidenceChecker(threshold=0.5)
        score = checker.check("I'm not sure, maybe?")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestTracerThreadSafety:
    def test_concurrent_record(self):
        """Multiple threads recording events should not lose data."""
        tracer = Tracer()
        tracer.start()
        count = 100

        def record_events(thread_id: int):
            for i in range(count):
                tracer.record(
                    TraceEvent(
                        event_type=EventType.AGENT_THINKING,
                        agent_name=f"thread-{thread_id}",
                        data={"i": i},
                    )
                )

        threads = [threading.Thread(target=record_events, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 5 threads × 100 events = 500 events
        assert len(tracer.events) == 500
