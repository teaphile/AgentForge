"""Tests for the Forge orchestrator."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import yaml

from agentforge.core.forge import Forge
from agentforge.config.loader import ConfigError


@pytest.fixture
def minimal_yaml(tmp_path):
    config = {
        "team": {
            "name": "Test Team",
            "llm": "openai/gpt-4o-mini",
        },
        "agents": {
            "helper": {
                "role": "Helper",
                "goal": "Help people",
            },
        },
        "workflow": {
            "steps": [
                {
                    "id": "help",
                    "agent": "helper",
                    "task": "{{input}}",
                }
            ],
        },
    }
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.dump(config))
    return str(path)


class TestForgeInit:
    def test_from_yaml(self, minimal_yaml):
        forge = Forge.from_yaml(minimal_yaml)
        assert forge is not None

    def test_from_dict(self, sample_config):
        forge = Forge.from_dict(sample_config)
        assert forge is not None

    def test_from_yaml_nonexistent(self):
        with pytest.raises(ConfigError):
            Forge.from_yaml("/nonexistent.yaml")


class TestForgeRun:
    @patch("agentforge.llm.router.litellm")
    def test_run_returns_result(self, mock_litellm, sample_config):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test output"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "openai/gpt-4o-mini"
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.completion_cost = MagicMock(return_value=0.001)

        forge = Forge.from_dict(sample_config)
        result = forge.run(task="Hello")
        assert result is not None
