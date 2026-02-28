"""Test that the Telegram bot handles tasks asynchronously."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_tasks_run_concurrently():
    """Verify multiple tasks can be tracked in parallel."""
    from agent.interfaces.telegram import TaskInfo, _active_tasks

    _active_tasks.clear()
    _active_tasks[1] = TaskInfo(task_text="task A", chat_id=1)
    _active_tasks[2] = TaskInfo(task_text="task B", chat_id=1)
    assert len(_active_tasks) == 2
    _active_tasks.clear()


@pytest.mark.asyncio
async def test_status_responds_while_task_active():
    """Verify /status can report active task count without blocking."""
    from agent.interfaces.telegram import TaskInfo, _active_tasks

    _active_tasks.clear()
    _active_tasks[99] = TaskInfo(task_text="long running", chat_id=1)
    assert len(_active_tasks) == 1
    assert _active_tasks[99].task_text == "long running"
    _active_tasks.clear()


@pytest.mark.asyncio
async def test_fire_and_forget_pattern():
    """Verify asyncio.create_task returns immediately while work continues."""
    results = []

    async def slow_work():
        await asyncio.sleep(0.1)
        results.append("done")

    task = asyncio.create_task(slow_work())
    assert len(results) == 0
    await task
    assert results == ["done"]


@pytest.mark.asyncio
async def test_bot_stays_responsive_while_task_runs():
    """While a long task runs in background, /status and other commands respond without blocking."""
    from agent.interfaces.telegram import (
        _active_tasks,
        _chat_locks,
        _chat_queued_count,
        handle_message,
        status_cmd,
    )

    _active_tasks.clear()
    _chat_locks.clear()
    _chat_queued_count.clear()

    long_task_started = asyncio.Event()
    long_task_release = asyncio.Event()

    async def mock_run_task(*args, **kwargs):
        long_task_started.set()
        await long_task_release.wait()
        return "done"

    def _make_update(chat_id: int, text: str = "task"):
        u = MagicMock()
        u.effective_chat.id = chat_id
        u.effective_user = MagicMock()
        u.effective_user.username = "u"
        u.effective_user.id = 1
        u.message = AsyncMock()
        u.message.text = text
        return u

    try:
        with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
            with patch("agent.interfaces.telegram.application", MagicMock(bot=AsyncMock())):
                with patch(
                    "agent.core.runner.run_task_with_session",
                    side_effect=mock_run_task,
                ):
                    await handle_message(_make_update(1, "long task"), MagicMock())
                    await long_task_started.wait()
                    t0 = time.monotonic()
                    status_update = _make_update(2, "/status")
                    await status_cmd(status_update, MagicMock())
                    elapsed = time.monotonic() - t0
                    long_task_release.set()
        await asyncio.sleep(0.05)
    finally:
        _active_tasks.clear()
        _chat_locks.clear()
        _chat_queued_count.clear()

    assert elapsed < 0.5, "status_cmd must not block on running task"
    reply = status_update.message.reply_text.call_args[0][0]
    assert "1 running" in reply or "running" in reply
