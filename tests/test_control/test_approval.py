"""Tests for approval control."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from agentforge.control.approval import ApprovalManager, ApprovalResult


class TestApprovalResult:
    def test_approved(self):
        result = ApprovalResult(approved=True, reason="Looks good")
        assert result.approved is True
        assert result.reason == "Looks good"

    def test_rejected(self):
        result = ApprovalResult(approved=False, reason="Too risky")
        assert result.approved is False


class TestApprovalManager:
    def test_init_cli_mode(self):
        mgr = ApprovalManager(mode="cli")
        assert mgr.mode == "cli"

    def test_init_dashboard_mode(self):
        mgr = ApprovalManager(mode="dashboard")
        assert mgr.mode == "dashboard"

    @pytest.mark.asyncio
    @patch("agentforge.control.approval.Prompt.ask", return_value="a")
    async def test_cli_approve(self, mock_ask):
        mgr = ApprovalManager(mode="cli")
        result = await mgr.request_approval("step1", "agent1", "Action", "output text")
        assert result.approved is True

    @pytest.mark.asyncio
    @patch("agentforge.control.approval.Prompt.ask", return_value="r")
    async def test_cli_reject(self, mock_ask):
        mgr = ApprovalManager(mode="cli")
        result = await mgr.request_approval("step1", "agent1", "Action", "output text")
        assert result.approved is False
