"""Tests for defaults merge and schema validation edge cases."""

from __future__ import annotations

import copy

from agentforge.config.defaults import DEFAULTS, merge_with_defaults


class TestDeepMerge:
    def test_defaults_not_mutated(self):
        """Merging should never modify DEFAULTS in place."""
        original = copy.deepcopy(DEFAULTS)
        merge_with_defaults({"team": {"name": "Custom"}})
        assert DEFAULTS == original

    def test_override_nested_key(self):
        result = merge_with_defaults({
            "team": {"memory": {"backend": "chromadb"}},
        })
        assert result["team"]["memory"]["backend"] == "chromadb"
        # Other nested keys should still have defaults
        assert result["team"]["memory"]["enabled"] is True

    def test_override_top_level(self):
        result = merge_with_defaults({"team": {"name": "MyTeam"}})
        assert result["team"]["name"] == "MyTeam"

    def test_preserves_extra_keys(self):
        result = merge_with_defaults({"custom_key": "custom_value"})
        assert result["custom_key"] == "custom_value"

    def test_repeated_merges_independent(self):
        """Two sequential merges should not interfere with each other."""
        r1 = merge_with_defaults({"team": {"name": "A"}})
        r2 = merge_with_defaults({"team": {"name": "B"}})
        assert r1["team"]["name"] == "A"
        assert r2["team"]["name"] == "B"
