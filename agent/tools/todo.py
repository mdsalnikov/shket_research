"""TODO list tools for step-by-step task execution."""

from __future__ import annotations

import json
import logging
import os

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

TODO_FILE = os.path.join(PROJECT_ROOT, ".agent_todo.json")


def _load() -> dict:
    if not os.path.exists(TODO_FILE):
        return {"tasks": [], "done": []}
    with open(TODO_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(TODO_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def create_todo(tasks: list[str]) -> str:
    """Create a TODO list for a multi-step task. Overwrites any existing TODO.

    Args:
        tasks: List of task descriptions (strings). Each becomes one step.
    """
    with log_tool_call("create_todo", f"{len(tasks)} steps") as tool_log:
        logger.info("Tool create_todo: %d steps", len(tasks))
        data = {"tasks": tasks, "done": []}
        _save(data)
        lines = [f"{i + 1}. [ ] {t}" for i, t in enumerate(tasks)]
        full = "TODO created:\n" + "\n".join(lines)
        tool_log.log_result(f"{len(tasks)} steps")
        return full


async def get_todo() -> str:
    """Get current TODO list with completion status."""
    with log_tool_call("get_todo") as tool_log:
        logger.info("Tool get_todo")
        data = _load()
        tasks = data.get("tasks", [])
        done = set(data.get("done", []))
        if not tasks:
            tool_log.log_result("empty")
            return "No TODO list. Use create_todo to start one."
        lines = [f"{i + 1}. {'[x]' if i in done else '[ ]'} {t}" for i, t in enumerate(tasks)]
        full = "TODO:\n" + "\n".join(lines)
        tool_log.log_result(f"{len(done)}/{len(tasks)} done")
        return full


async def mark_todo_done(step_index: int) -> str:
    """Mark a TODO step as done. step_index is 1-based (first step = 1).

    Args:
        step_index: Step number (1, 2, 3, ...).
    """
    with log_tool_call("mark_todo_done", f"step {step_index}") as tool_log:
        logger.info("Tool mark_todo_done: %d", step_index)
        data = _load()
        tasks = data.get("tasks", [])
        done = set(data.get("done", []))
        idx = step_index - 1
        if idx < 0 or idx >= len(tasks):
            tool_log.log_result(f"invalid step {step_index}")
            return f"Invalid step_index {step_index}. Valid range: 1..{len(tasks)}"
        done.add(idx)
        data["done"] = sorted(done)
        _save(data)
        remaining = len(tasks) - len(done)
        [f"{i + 1}. {'[x]' if i in done else '[ ]'} {t}" for i, t in enumerate(tasks)]
        tool_log.log_result(f"{len(done)}/{len(tasks)} done, {remaining} remaining")
        return f"Step {step_index} marked done. {remaining} steps remaining."
