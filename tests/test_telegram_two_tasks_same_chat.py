"""Test two messages from same user (same chat): run in order, responses in order."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.interfaces.telegram import (
    _active_tasks,
    _chat_locks,
    _chat_queued_count,
    handle_message,
)


def _make_update(chat_id: int, text: str, username: str = "testuser"):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user = MagicMock()
    update.effective_user.username = username
    update.effective_user.id = 1
    update.message = AsyncMock()
    update.message.text = text
    return update


@pytest.fixture(autouse=True)
def reset_globals():
    _active_tasks.clear()
    _chat_locks.clear()
    _chat_queued_count.clear()
    yield
    _active_tasks.clear()
    _chat_locks.clear()
    _chat_queued_count.clear()


@pytest.mark.asyncio
async def test_two_tasks_same_chat_run_sequentially():
    """First task runs to completion, then second; run_task_with_session called in order."""
    call_order = []
    results = []
    mock_bot = AsyncMock()

    async def mock_run_task(
        text, chat_id, username=None, user_id=None, provider=None, resumable_task_id=None, **kwargs
    ):
        call_order.append(text)
        if "first" in text:
            await asyncio.sleep(0.1)
            results.append("result_first")
            return "result_first"
        results.append("result_second")
        return "result_second"

    with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
        with patch("agent.interfaces.telegram.application", MagicMock(bot=mock_bot)):
            with patch("agent.core.runner.run_task_with_session", side_effect=mock_run_task):
                ctx = MagicMock()
                u1 = _make_update(chat_id=100, text="first task")
                u2 = _make_update(chat_id=100, text="second task")
                await handle_message(u1, ctx)
                await handle_message(u2, ctx)
                for _ in range(100):
                    await asyncio.sleep(0.02)
                    if len(call_order) == 2 and len(_active_tasks) == 0:
                        break

    assert call_order == ["first task", "second task"]
    assert results == ["result_first", "result_second"]
    all_text = " ".join(str(c) for c in mock_bot.send_message.call_args_list)
    assert "result_first" in all_text
    assert "result_second" in all_text
