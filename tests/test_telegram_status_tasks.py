"""Tests for /status and /tasks showing running and queued counts."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.interfaces.telegram import (
    status_cmd,
    tasks_cmd,
    _active_tasks,
    _chat_queued_count,
    TaskInfo,
)


def _make_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.username = "testuser"
    update.message = AsyncMock()
    return update


@pytest.fixture(autouse=True)
def reset_globals():
    _active_tasks.clear()
    _chat_queued_count.clear()
    yield
    _active_tasks.clear()
    _chat_queued_count.clear()


@pytest.mark.asyncio
async def test_status_shows_running_and_queued():
    _active_tasks[1] = TaskInfo(task_text="task A", chat_id=10)
    _active_tasks[2] = TaskInfo(task_text="task B", chat_id=20)
    _chat_queued_count[10] = 1
    _chat_queued_count[30] = 2

    with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
        update = _make_update()
        await status_cmd(update, MagicMock())

    text = update.message.reply_text.call_args[0][0]
    assert "2 running" in text
    assert "3 queued" in text


@pytest.mark.asyncio
async def test_tasks_shows_running_and_queued_by_chat():
    _active_tasks[1] = TaskInfo(task_text="running task", chat_id=10, provider="openrouter")
    _chat_queued_count[10] = 2
    _chat_queued_count[20] = 1

    with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
        update = _make_update()
        await tasks_cmd(update, MagicMock())

    text = update.message.reply_text.call_args[0][0]
    assert "1 running" in text
    assert "10" in text and "2" in text and "20" in text and "1" in text
    assert "running task" in text


@pytest.mark.asyncio
async def test_tasks_empty_when_no_running_no_queued():
    with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
        update = _make_update()
        await tasks_cmd(update, MagicMock())

    text = update.message.reply_text.call_args[0][0]
    assert "No active tasks" in text
