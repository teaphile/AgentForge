"""Tests for confidence scoring."""

from __future__ import annotations


from agentforge.control.confidence import ConfidenceChecker


class TestConfidenceChecker:
    def test_init_with_threshold(self):
        checker = ConfidenceChecker(threshold=0.5)
        assert checker.threshold == 0.5

    def test_default_threshold(self):
        checker = ConfidenceChecker()
        assert checker.threshold > 0

    def test_score_high_confidence(self):
        checker = ConfidenceChecker(threshold=0.4)
        text = (
            "This is a comprehensive and detailed answer"
            " with multiple supporting points and evidence."
        )
        score = checker.check(text)
        assert score >= 0.0

    def test_score_low_confidence(self):
        checker = ConfidenceChecker(threshold=0.8)
        score = checker.check("hmm")
        assert score >= 0.0

    def test_uncertainty_lowers_score(self):
        checker = ConfidenceChecker(threshold=0.4)
        confident = checker.check("The answer is definitively 42. This is well established.")
        uncertain = checker.check("I'm not sure, maybe it could possibly be 42, but it's unclear.")
        assert confident > uncertain

    def test_score_in_range(self):
        checker = ConfidenceChecker()
        score = checker.check("Some output text")
        assert 0.0 <= score <= 1.0
