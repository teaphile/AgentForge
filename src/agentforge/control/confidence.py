"""Heuristic confidence scoring for agent outputs."""

from __future__ import annotations


class ConfidenceChecker:

    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold

    def check(self, output: str) -> float:
        """Estimate confidence from the output text using keyword heuristics."""
        uncertainty_phrases = [
            "i'm not sure",
            "i am not sure",
            "i don't know",
            "i'm unsure",
            "uncertain",
            "not confident",
            "possibly",
            "maybe",
            "might be",
            "hard to say",
            "difficult to determine",
            "unclear",
            "i think",
            "it seems",
            "perhaps",
        ]

        output_lower = output.lower()

        # Start with base confidence
        confidence = 0.7

        # Check for uncertainty phrases
        uncertainty_count = sum(1 for phrase in uncertainty_phrases if phrase in output_lower)
        confidence -= uncertainty_count * 0.1

        # Boost for longer, detailed output
        word_count = len(output.split())
        if word_count > 200:
            confidence += 0.1
        elif word_count < 20:
            confidence -= 0.1

        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        return confidence

    def should_pause(self, output: str) -> bool:
        return self.check(output) < self.threshold
