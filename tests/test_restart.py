"""Tests for restart tool and TG handler integration."""

import pytest

from agent.tools import restart


@pytest.mark.asyncio
async def test_request_restart_sets_flag():
    """request_restart sets RESTART_REQUESTED to True."""
    restart.RESTART_REQUESTED = False
    out = await restart.request_restart()
    assert restart.RESTART_REQUESTED is True
    assert "restart" in out.lower()
    restart.RESTART_REQUESTED = False


def test_restart_flag_module_attribute():
    """RESTART_REQUESTED is a module-level attribute."""
    assert hasattr(restart, "RESTART_REQUESTED")
    restart.RESTART_REQUESTED = False
    assert restart.RESTART_REQUESTED is False
