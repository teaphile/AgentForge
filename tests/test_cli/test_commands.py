"""Tests for CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from agentforge.cli.commands import app


runner = CliRunner()


class TestVersionCommand:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout or "agentforge" in result.stdout.lower()


class TestValidateCommand:
    def test_validate_nonexistent(self):
        result = runner.invoke(app, ["validate", "/nonexistent.yaml"])
        assert result.exit_code != 0 or "error" in result.stdout.lower() or "not found" in result.stdout.lower()


class TestInitCommand:
    def test_init(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path / "test_project")])
        assert result.exit_code == 0
        assert (tmp_path / "test_project" / "agents.yaml").exists()
