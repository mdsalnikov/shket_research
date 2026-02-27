"""Agent task runner with self-healing retries."""

from __future__ import annotations

import logging

from agent.config import MAX_RETRIES

logger = logging.getLogger(__name__)


async def run_with_retry(task: str, max_retries: int | None = None) -> str:
    """Run agent task; on failure, retry with error context up to max_retries times.

    Args:
        task: Initial task description.
        max_retries: Override config (default: MAX_RETRIES from config).

    Returns:
        Agent output. On final failure: error summary with attempt count and last error.
    """
    from agent.core.agent import build_agent

    n = max_retries if max_retries is not None else MAX_RETRIES
    current_task = task
    last_error: Exception | None = None

    for attempt in range(n):
        try:
            agent = build_agent()
            result = await agent.run(current_task)
            return result.output
        except Exception as e:
            last_error = e
            logger.warning("Attempt %d/%d failed: %s", attempt + 1, n, e)
            if attempt < n - 1:
                current_task = (
                    f"{task}\n\n"
                    f"[Попытка {attempt + 1}/{n} не удалась: {e}. "
                    f"Исправь проблему и выполни задачу снова.]"
                )
            else:
                break

    msg = (
        f"Не удалось выполнить задачу после {n} попыток.\n\n"
        f"Последняя ошибка: {last_error}"
    )
    logger.error("Task failed after %d attempts: %s", n, last_error)
    return msg
