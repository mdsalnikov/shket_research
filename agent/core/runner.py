"""Agent task runner with session support and self-healing retries.

This module provides the main entry points for running agent tasks
with SQLite session persistence (OpenClaw-inspired architecture).
"""

from __future__ import annotations

import logging

from agent.config import MAX_RETRIES
from agent.dependencies import AgentDeps
from agent.session_globals import close_db

logger = logging.getLogger(__name__)


async def run_with_retry(
    task: str,
    max_retries: int | None = None,
    chat_id: int = 0,
    deps: AgentDeps | None = None,
) -> str:
    """Run agent task with session support; on failure, retry with error context.

    This is the core runner function that handles retries and session management.
    
    Args:
        task: Initial task description.
        max_retries: Override config (default: MAX_RETRIES from config).
        chat_id: Chat ID for session isolation (default: 0 for CLI).
        deps: Pre-created dependencies (optional, will create if not provided).

    Returns:
        Agent output. On final failure: error summary with attempt count and last error.
        
    Example:
        result = await run_with_retry("list files in /tmp", chat_id=12345)
        
    """
    from agent.core.agent import build_session_agent

    n = max_retries if max_retries is not None else MAX_RETRIES
    current_task = task
    last_error: Exception | None = None
    agent = build_session_agent()

    # Create dependencies if not provided
    if deps is None:
        deps = await AgentDeps.create(chat_id=chat_id)

    # Log user message to session
    await deps.add_user_message(task)

    try:
        for attempt in range(n):
            try:
                logger.info(f"Running task (attempt {attempt + 1}/{n})")
                result = await agent.run(current_task, deps=deps)

                # Log assistant response
                await deps.add_assistant_message(result.output)

                logger.info(f"Task completed successfully")
                return result.output

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{n} failed: {e}")
                deps.last_error = str(e)
                deps.retry_count = attempt + 1

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
        logger.error(f"Task failed after {n} attempts: {last_error}")
        return msg

    finally:
        # Don't close DB here - it's a global singleton
        # DB will be closed on application shutdown
        pass


async def run_task_with_session(
    task: str,
    chat_id: int,
    username: str | None = None,
    user_id: int | None = None,
    session_scope: str = "main",
) -> str:
    """Run a task with full session management.

    This is the preferred entry point for running agent tasks with
    SQLite session persistence and memory support.

    OpenClaw-inspired architecture:
    - Sessions are isolated per chat_id and scope
    - Conversation history is persisted in SQLite
    - Memory (L0/L1/L2) is available across sessions
    - User context is preserved for personalization

    Args:
        task: Task description
        chat_id: Telegram chat ID for session isolation
        username: Optional user display name
        user_id: Optional Telegram user ID
        session_scope: Session scope (main/per-peer/per-channel-peer)

    Returns:
        Agent response
        
    Example:
        response = await run_task_with_session(
            "what files are in /tmp?",
            chat_id=12345,
            username="john",
        )
        
    """
    deps = await AgentDeps.create(
        chat_id=chat_id,
        username=username,
        user_id=user_id,
        session_scope=session_scope,
    )

    return await run_with_retry(task, deps=deps)


async def run_simple_task(task: str, model_name: str | None = None) -> str:
    """Run a simple task without session persistence.
    
    Useful for one-off tasks that don't need session isolation
    or memory persistence.
    
    Args:
        task: Task description
        model_name: Optional model override
        
    Returns:
        Agent response
        
    """
    from agent.core.agent import build_agent

    agent = build_agent(model_name=model_name)
    
    try:
        result = await agent.run(task)
        return result.output
    except Exception as e:
        logger.error(f"Simple task failed: {e}")
        return f"Error: {e}"


async def cleanup():
    """Cleanup resources on application shutdown.
    
    Closes the database connection and any other resources.
    Should be called when the application is shutting down.
    
    """
    await close_db()
    logger.info("Runner cleanup completed")
