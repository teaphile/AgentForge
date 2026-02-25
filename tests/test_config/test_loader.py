"""Tests for config loader."""

from __future__ import annotations

import pytest
import yaml

from agentforge.config.loader import ConfigLoader, ConfigError


@pytest.fixture
def valid_yaml_file(sample_config, tmp_path):
    """Create a temporary YAML file with valid config."""
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.dump(sample_config, default_flow_style=False))
    return str(path)


@pytest.fixture
def invalid_yaml_file(tmp_path):
    """Create a temporary YAML file with invalid YAML."""
    path = tmp_path / "bad.yaml"
    path.write_text("team:\n  name: Test\n  invalid_indent: [\n")
    return str(path)


class TestConfigLoaderLoad:
    def test_load_valid_yaml(self, valid_yaml_file):
        data = ConfigLoader.load(valid_yaml_file)
        assert isinstance(data, dict)
        assert "team" in data
        assert "agents" in data
        assert "workflow" in data

    def test_load_nonexistent_file(self):
        with pytest.raises(ConfigError):
            ConfigLoader.load("/nonexistent/agents.yaml")

    def test_load_invalid_yaml(self, invalid_yaml_file):
        with pytest.raises(ConfigError):
            ConfigLoader.load(invalid_yaml_file)


class TestConfigLoaderValidate:
    def test_validate_valid_config(self, sample_config):
        config = ConfigLoader.validate(sample_config)
        assert config is not None

    def test_validate_missing_agents(self):
        # Defaults add a team, but missing agents should still fail
        with pytest.raises(ConfigError):
            ConfigLoader.validate({"workflow": {"steps": []}})

    def test_validate_missing_workflow(self):
        with pytest.raises(ConfigError):
            ConfigLoader.validate({"agents": {"a": {"role": "R", "goal": "G"}}})

    def test_validate_returns_dict(self, sample_config):
        config = ConfigLoader.validate(sample_config)
        assert isinstance(config, dict)
