"""Tests for run_with_retry self-healing."""

from unittest.mock import AsyncMock, patch

import pytest

from agent.core.runner import run_with_retry


@pytest.mark.asyncio
async def test_run_succeeds_first_try():
    """When agent succeeds, no retries."""
    with patch("agent.core.agent.build_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = type("R", (), {"output": "done"})()
        mock_build.return_value = mock_agent

        out = await run_with_retry("task", max_retries=3)
        assert out == "done"
        assert mock_agent.run.call_count == 1


@pytest.mark.asyncio
async def test_run_retries_on_failure():
    """When agent fails, retries with error context."""
    with patch("agent.core.agent.build_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = [
            ValueError("first fail"),
            type("R", (), {"output": "recovered"})(),
        ]
        mock_build.return_value = mock_agent

        out = await run_with_retry("task", max_retries=3)
        assert out == "recovered"
        assert mock_agent.run.call_count == 2


@pytest.mark.asyncio
async def test_run_gives_up_after_max_retries():
    """After max retries, returns error summary."""
    with patch("agent.core.agent.build_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = ValueError("persistent fail")
        mock_build.return_value = mock_agent

        out = await run_with_retry("task", max_retries=2)
        assert "2 попыток" in out or "2 attempts" in out or "2" in out
        assert "persistent fail" in out
        assert mock_agent.run.call_count == 2
