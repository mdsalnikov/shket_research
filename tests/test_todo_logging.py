"""Test that TODO is logged to agent log."""

import logging
import os

import pytest

from agent.config import LOG_FILE, setup_logging
from agent.tools.todo import create_todo, get_todo


@pytest.mark.asyncio
async def test_create_todo_logs_to_file():
    """create_todo writes full TODO to agent log."""
    setup_logging()
    await create_todo(["step a", "step b"])
    await get_todo()
    logging.shutdown()

    with open(LOG_FILE) as f:
        content = f.read()
    assert "[TODO]" in content
    assert "step a" in content or "step b" in content
