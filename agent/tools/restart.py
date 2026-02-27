"""Restart tool: request process restart after self-modification (TG bot only)."""

from __future__ import annotations

import logging

from agent.activity_log import log_tool_call

logger = logging.getLogger(__name__)

RESTART_REQUESTED = False


async def request_restart() -> str:
    """Request restart of the current process to load new code.

    Call this AFTER successful self-modification, tests, and git commit.
    Only works when running as TG bot — the bot will restart with the new code.
    CLI runs are one-shot; no restart needed.
    """
    global RESTART_REQUESTED
    with log_tool_call("request_restart") as tool_log:
        logger.info("Tool request_restart")
        RESTART_REQUESTED = True
        tool_log.log_result("restart scheduled")
        return "Restart requested. Bot will restart with new code after this response."
