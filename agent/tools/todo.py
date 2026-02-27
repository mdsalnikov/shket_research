"""TODO list tools for step-by-step task execution."""

from __future__ import annotations

import json
import logging
import os

from agent.config import LOG_FILE, PROJECT_ROOT

logger = logging.getLogger(__name__)

TODO_FILE = os.path.join(PROJECT_ROOT, ".agent_todo.json")


def _log_todo(content: str) -> None:
    """Log full TODO to agent log file."""
    logger.info("TODO: %s", content.replace("\n", " | "))
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[TODO] {content}\n")
    except Exception:
        pass


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
    full = "TODO created:\n" + "\n".join(lines)
    _log_todo(full)
    return full


async def get_todo() -> str:
    """Get current TODO list with completion status."""
    logger.info("Tool get_todo")
    data = _load()
    tasks = data.get("tasks", [])
    done = set(data.get("done", []))
    if not tasks:
        return "No TODO list. Use create_todo to start one."
    lines = [f"{i+1}. {'[x]' if i in done else '[ ]'} {t}" for i, t in enumerate(tasks)]
    full = "TODO:\n" + "\n".join(lines)
    _log_todo(full)
    return full


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
    lines = [f"{i+1}. {'[x]' if i in done else '[ ]'} {t}" for i, t in enumerate(tasks)]
    _log_todo("TODO:\n" + "\n".join(lines))
    return f"Step {step_index} marked done. {remaining} steps remaining."
