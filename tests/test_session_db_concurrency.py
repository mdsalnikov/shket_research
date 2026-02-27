"""Tests for SessionDB lock: concurrent reads/writes stay consistent."""

import asyncio
import os
import tempfile

import pytest

from agent.session_db import SessionDB


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


@pytest.mark.asyncio
async def test_session_db_lock_serializes_concurrent_reads_writes(session_db):
    """Reader never sees half-written message_history_json."""
    session_id = await session_db.get_or_create_session(99999)
    seen = []
    read_errors = []

    async def writer():
        for i in range(20):
            await session_db.set_model_message_history(session_id, f'{{"v":{i}}}')
            await asyncio.sleep(0.001)

    async def reader():
        for _ in range(30):
            try:
                raw = await session_db.get_model_message_history(session_id)
                if raw:
                    seen.append(raw)
            except Exception as e:
                read_errors.append(e)
            await asyncio.sleep(0.001)

    await asyncio.gather(writer(), reader())
    assert not read_errors
    for s in seen:
        assert s is not None and "v" in s


@pytest.mark.asyncio
async def test_get_messages_under_lock(session_db):
    """Concurrent add_message and get_messages yield consistent count and order."""
    session_id = await session_db.get_or_create_session(88888)
    counts = []

    async def add_n(n):
        for i in range(n):
            await session_db.add_message(session_id, "user", f"msg_{i}")
            await asyncio.sleep(0.001)

    async def read_counts():
        for _ in range(15):
            messages = await session_db.get_messages(session_id)
            counts.append(len(messages))
            await asyncio.sleep(0.002)

    await asyncio.gather(add_n(10), read_counts())
    assert counts[-1] == 10
    messages = await session_db.get_messages(session_id)
    assert len(messages) == 10
    for i, m in enumerate(messages):
        assert m.content == f"msg_{i}"
