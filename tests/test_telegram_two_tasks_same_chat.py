"""Test two messages from same user (same chat): run in order, responses in order."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.interfaces.telegram import (
    handle_message,
    _active_tasks,
    _chat_locks,
    _chat_queued_count,
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

    async def mock_run_task(text, chat_id, username=None, user_id=None, provider=None, resumable_task_id=None, **kwargs):
        call_order.append(text)
        if "first" in text:
            await asyncio.sleep(0.1)
            results.append("result_first")
            return "result_first"
        results.append("result_second")
        return "result_second"

    with patch("agent.interfaces.telegram._is_user_allowed", return_value=True):
        with patch("agent.core.runner.run_task_with_session", side_effect=mock_run_task):
            ctx = MagicMock()
            u1 = _make_update(chat_id=100, text="first task")
            u2 = _make_update(chat_id=100, text="second task")
            t1 = asyncio.create_task(handle_message(u1, ctx))
            t2 = asyncio.create_task(handle_message(u2, ctx))
            await asyncio.gather(t1, t2)

    assert call_order == ["first task", "second task"]
    assert results == ["result_first", "result_second"]
    u1_calls = [str(c[0][0]) for c in u1.message.reply_text.call_args_list]
    u2_calls = [str(c[0][0]) for c in u2.message.reply_text.call_args_list]
    assert any("result_first" in s for s in u1_calls)
    assert any("result_second" in s for s in u2_calls)
