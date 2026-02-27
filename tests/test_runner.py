"""Tests for run_with_retry self-healing."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest


@pytest.mark.asyncio
async def test_run_succeeds_first_try():
    """When agent succeeds, no retries."""
    from agent.core.runner import run_with_retry

    with patch("agent.core.agent.build_session_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "done"
        mock_agent.run.return_value = mock_result
        mock_build.return_value = mock_agent

        # Mock AgentDeps
        with patch("agent.core.runner.AgentDeps") as mock_deps_class:
            mock_deps = AsyncMock()
            mock_deps.add_user_message = AsyncMock()
            mock_deps.add_assistant_message = AsyncMock()
            mock_deps_class.create = AsyncMock(return_value=mock_deps)

            out = await run_with_retry("task", max_retries=3)
            assert out == "done"
            assert mock_agent.run.call_count == 1


@pytest.mark.asyncio
async def test_run_retries_on_failure():
    """When agent fails, retries with error context."""
    from agent.core.runner import run_with_retry

    with patch("agent.core.agent.build_session_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "recovered"
        mock_agent.run.side_effect = [
            ValueError("first fail"),
            mock_result,
        ]
        mock_build.return_value = mock_agent

        # Mock AgentDeps
        with patch("agent.core.runner.AgentDeps") as mock_deps_class:
            mock_deps = AsyncMock()
            mock_deps.add_user_message = AsyncMock()
            mock_deps.add_assistant_message = AsyncMock()
            mock_deps_class.create = AsyncMock(return_value=mock_deps)

            out = await run_with_retry("task", max_retries=3)
            assert out == "recovered"
            assert mock_agent.run.call_count == 2


@pytest.mark.asyncio
async def test_run_gives_up_after_max_retries():
    """After max retries, returns error summary."""
    from agent.core.runner import run_with_retry

    with patch("agent.core.agent.build_session_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = ValueError("persistent fail")
        mock_build.return_value = mock_agent

        # Mock AgentDeps
        with patch("agent.core.runner.AgentDeps") as mock_deps_class:
            mock_deps = AsyncMock()
            mock_deps.add_user_message = AsyncMock()
            mock_deps.add_assistant_message = AsyncMock()
            mock_deps_class.create = AsyncMock(return_value=mock_deps)

            out = await run_with_retry("task", max_retries=2)
            assert "2" in out
            assert "persistent fail" in out
            assert mock_agent.run.call_count == 2
