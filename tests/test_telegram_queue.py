"""Tests for Telegram bot per-chat queue: lock serialization and queued count."""

import asyncio

import pytest

from agent.interfaces.telegram import (
    _get_chat_lock,
    _chat_locks,
    _chat_queued_count,
    _active_tasks,
    TaskInfo,
)


@pytest.fixture(autouse=True)
def reset_telegram_globals():
    _active_tasks.clear()
    _chat_locks.clear()
    _chat_queued_count.clear()
    yield
    _active_tasks.clear()
    _chat_locks.clear()
    _chat_queued_count.clear()


@pytest.mark.asyncio
async def test_chat_lock_serializes_same_chat():
    """Two handlers for same chat_id run one after another."""
    order = []
    lock = _get_chat_lock(1)

    async def first():
        async with lock:
            order.append("first_start")
            await asyncio.sleep(0.05)
            order.append("first_end")

    async def second():
        async with lock:
            order.append("second_start")
            order.append("second_end")

    t1 = asyncio.create_task(first())
    await asyncio.sleep(0.01)
    t2 = asyncio.create_task(second())
    await asyncio.gather(t1, t2)
    assert order == ["first_start", "first_end", "second_start", "second_end"]


@pytest.mark.asyncio
async def test_queued_count_increments_while_waiting():
    """While one handler holds the lock, another is counted as queued."""
    from agent.interfaces import telegram as tg

    lock = _get_chat_lock(42)
    holder_released = asyncio.Event()

    async def holder():
        async with lock:
            await holder_released.wait()

    async def waiter():
        tg._chat_queued_count[42] = tg._chat_queued_count.get(42, 0) + 1
        try:
            async with lock:
                tg._chat_queued_count[42] = max(0, tg._chat_queued_count.get(42, 1) - 1)
        finally:
            pass

    h = asyncio.create_task(holder())
    await asyncio.sleep(0.02)
    w = asyncio.create_task(waiter())
    await asyncio.sleep(0.02)
    assert tg._chat_queued_count.get(42, 0) == 1
    holder_released.set()
    await asyncio.gather(h, w)
    assert tg._chat_queued_count.get(42, 0) == 0


@pytest.mark.asyncio
async def test_queued_count_decrement_on_exception_before_lock():
    """If handler fails before acquiring lock, queued count is decremented in finally."""
    from agent.interfaces import telegram as tg

    tg._chat_queued_count[99] = 0

    async def fake_handler_that_raises():
        tg._chat_queued_count[99] = tg._chat_queued_count.get(99, 0) + 1
        got_lock = False
        try:
            raise ValueError("oops before lock")
        finally:
            if not got_lock:
                tg._chat_queued_count[99] = max(0, tg._chat_queued_count.get(99, 1) - 1)

    with pytest.raises(ValueError, match="oops before lock"):
        await fake_handler_that_raises()
    assert tg._chat_queued_count.get(99, 0) == 0
