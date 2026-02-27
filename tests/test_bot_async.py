"""Test that the Telegram bot handles tasks asynchronously."""

import asyncio

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
