"""TODO list tools for step-by-step task execution."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

TODO_FILE = "/workspace/.agent_todo.json"


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
    logger.info("Tool create_todo: %d steps", len(tasks))
    data = {"tasks": tasks, "done": []}
    _save(data)
    lines = [f"{i+1}. [ ] {t}" for i, t in enumerate(tasks)]
    return "TODO created:\n" + "\n".join(lines)


async def get_todo() -> str:
    """Get current TODO list with completion status."""
    logger.info("Tool get_todo")
    data = _load()
    tasks = data.get("tasks", [])
    done = set(data.get("done", []))
    if not tasks:
        return "No TODO list. Use create_todo to start one."
    lines = []
    for i, t in enumerate(tasks):
        status = "[x]" if i in done else "[ ]"
        lines.append(f"{i+1}. {status} {t}")
    return "TODO:\n" + "\n".join(lines)


async def mark_todo_done(step_index: int) -> str:
    """Mark a TODO step as done. step_index is 1-based (first step = 1).

    Args:
        step_index: Step number (1, 2, 3, ...).
    """
    logger.info("Tool mark_todo_done: %d", step_index)
    data = _load()
    tasks = data.get("tasks", [])
    done = set(data.get("done", []))
    idx = step_index - 1
    if idx < 0 or idx >= len(tasks):
        return f"Invalid step_index {step_index}. Valid range: 1..{len(tasks)}"
    done.add(idx)
    data["done"] = sorted(done)
    _save(data)
    remaining = len(tasks) - len(done)
    return f"Step {step_index} marked done. {remaining} steps remaining."
