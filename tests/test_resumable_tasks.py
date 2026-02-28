"""Tests for resumable tasks: DB, runner integration, resume flow, edge cases."""

import asyncio
import os
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.session_db import SessionDB
from agent.core.runner import (
    run_task_with_session,
    run_with_retry,
    AUTO_REPAIR_TASK_PREFIX,
    _build_repair_goal,
    _should_create_repair_task,
)
from agent.interfaces.telegram import (
    _build_resume_prompt,
    _do_resume,
    MAX_RESUME_COUNT,
)


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
async def session_db(temp_db):
    db = SessionDB(temp_db)
    await db.init()
    yield db
    await db.close()


# ---------- SessionDB unit ----------

@pytest.mark.asyncio
async def test_upsert_resumable_task_returns_id(session_db):
    session_id = await session_db.get_or_create_session(999)
    rid = await session_db.upsert_resumable_task(session_id, 999, "My goal")
    assert rid > 0


@pytest.mark.asyncio
async def test_get_incomplete_returns_running(session_db):
    session_id = await session_db.get_or_create_session(888)
    await session_db.upsert_resumable_task(session_id, 888, "Goal A")
    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 1
    assert incomplete[0]["goal"] == "Goal A"
    assert incomplete[0]["status"] == "running"


@pytest.mark.asyncio
async def test_mark_completed_removes_from_incomplete(session_db):
    session_id = await session_db.get_or_create_session(777)
    rid = await session_db.upsert_resumable_task(session_id, 777, "Goal")
    await session_db.mark_resumable_task_completed(rid)
    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 0


@pytest.mark.asyncio
async def test_upsert_same_session_cancels_previous_running(session_db):
    session_id = await session_db.get_or_create_session(666)
    await session_db.upsert_resumable_task(session_id, 666, "First")
    await session_db.upsert_resumable_task(session_id, 666, "Second")
    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 1
    assert incomplete[0]["goal"] == "Second"


@pytest.mark.asyncio
async def test_increment_resume_and_set_resumed_at(session_db):
    session_id = await session_db.get_or_create_session(555)
    rid = await session_db.upsert_resumable_task(session_id, 555, "Goal")
    await session_db.increment_resume_and_set_resumed_at(rid)
    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 1
    assert incomplete[0]["resume_count"] == 1
    assert incomplete[0]["resumed_at"] is not None


# ---------- Runner integration ----------

@pytest.mark.asyncio
async def test_run_task_with_session_accepts_resumable_task_id(session_db):
    """run_task_with_session accepts resumable_task_id and passes it to run_with_retry (smoke)."""
    with patch("agent.session_globals.get_db", return_value=session_db):
        session_id = await session_db.get_or_create_session(111)
        rid = await session_db.upsert_resumable_task(session_id, 111, "Reply with OK")
    with patch("agent.core.runner.run_with_retry", AsyncMock(return_value="OK")) as mock_run:
        out = await run_task_with_session(
            "Reply with OK", chat_id=111, provider="vllm", resumable_task_id=rid
        )
        assert out == "OK"
        mock_run.assert_awaited_once()
        call_kw = mock_run.await_args[1]
        assert call_kw.get("resumable_task_id") == rid


# ---------- Resume prompt ----------

def test_build_resume_prompt_contains_goal_and_resume():
    prompt = _build_resume_prompt("Implement X", resume_count=2)
    assert "Resume" in prompt
    assert "Implement X" in prompt
    assert "Resume count: 2" in prompt


# ---------- _do_resume with mocks ----------

@pytest.mark.asyncio
async def test_do_resume_calls_run_and_mark_completed(session_db):
    bot = AsyncMock()
    task_row = {
        "id": 1,
        "session_id": 1,
        "chat_id": 333,
        "goal": "Goal",
        "resume_count": 0,
    }
    with patch("agent.session_globals.get_db", return_value=session_db):
        with patch("agent.core.runner.run_task_with_session", AsyncMock(return_value="Result")):
            await _do_resume(bot, task_row)
    assert bot.send_message.await_count >= 1
    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 0


@pytest.mark.asyncio
async def test_do_resume_max_resume_count_marks_failed_and_does_not_run(session_db):
    session_id = await session_db.get_or_create_session(444)
    rid = await session_db.upsert_resumable_task(session_id, 444, "Goal")
    for _ in range(MAX_RESUME_COUNT):
        await session_db.increment_resume_and_set_resumed_at(rid)
    row = (await session_db.get_incomplete_resumable_tasks())[0]
    assert row["resume_count"] == MAX_RESUME_COUNT
    bot = AsyncMock()
    with patch("agent.session_globals.get_db", return_value=session_db):
        with patch("agent.core.runner.run_task_with_session", AsyncMock()) as mock_run:
            await _do_resume(bot, row)
            mock_run.assert_not_awaited()
    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 0


# ---------- Auto-repair task creation ----------


def test_build_repair_goal_includes_context():
    goal = _build_repair_goal(
        original_task="Do X",
        last_error="Context overflow",
        partial_output="Step 1 done",
        attempt_count=3,
    )
    assert goal.startswith(AUTO_REPAIR_TASK_PREFIX)
    assert "Do X" in goal
    assert "Context overflow" in goal
    assert "Step 1 done" in goal
    assert "3" in goal


def test_should_create_repair_task_bot_chat():
    deps = MagicMock()
    deps.chat_id = 123
    assert _should_create_repair_task("Do something", deps) is True


def test_should_create_repair_task_skip_cli():
    deps = MagicMock()
    deps.chat_id = 0
    assert _should_create_repair_task("Do something", deps) is False


def test_should_create_repair_task_skip_already_repair():
    deps = MagicMock()
    deps.chat_id = 123
    assert _should_create_repair_task(f"{AUTO_REPAIR_TASK_PREFIX} fix it", deps) is False


@pytest.mark.asyncio
async def test_failure_creates_auto_repair_resumable_task(session_db):
    """When run fails (success=False) in bot context, a resumable repair task is created."""
    await session_db.get_or_create_session(200)
    with patch("agent.core.runner.SelfHealingRunner") as mock_runner_class:
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=("Partial output", False))
        mock_runner_class.return_value = mock_runner

        with patch("agent.dependencies.get_db", AsyncMock(return_value=session_db)):
            from agent.dependencies import AgentDeps
            deps = await AgentDeps.create(chat_id=200)
            deps.last_error = "Last error"
            deps.retry_count = 2

            with patch("agent.core.agent.build_session_agent", return_value=MagicMock()):
                out = await run_with_retry("Original user goal", deps=deps, max_retries=3)
                assert out == "Partial output"

    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 1
    assert incomplete[0]["goal"].startswith(AUTO_REPAIR_TASK_PREFIX)
    assert "Original user goal" in incomplete[0]["goal"]
    assert "Last error" in incomplete[0]["goal"]
    assert "Partial output" in incomplete[0]["goal"]


@pytest.mark.asyncio
async def test_repair_task_failure_does_not_create_second_repair(session_db):
    """When an auto-repair task itself fails, we do not create another repair (no chain)."""
    await session_db.get_or_create_session(201)
    repair_goal = f"{AUTO_REPAIR_TASK_PREFIX} Fix the thing. Original goal: X"
    with patch("agent.core.runner.SelfHealingRunner") as mock_runner_class:
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=("Still failed", False))
        mock_runner_class.return_value = mock_runner

        with patch("agent.session_globals.get_db", return_value=session_db):
            from agent.dependencies import AgentDeps
            deps = await AgentDeps.create(chat_id=201)
            deps.last_error = "Again"
            deps.retry_count = 1

            with patch("agent.core.agent.build_session_agent", return_value=MagicMock()):
                await run_with_retry(repair_goal, deps=deps, max_retries=2)

    incomplete = await session_db.get_incomplete_resumable_tasks()
    assert len(incomplete) == 0
