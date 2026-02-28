'''Agent task runner with session support and self-healing retries.

This module provides the main entry points for running agent tasks
with SQLite session persistence (OpenClaw-inspired architecture) and
intelligent self-healing error recovery.

Self-healing features:
- Error classification (recoverable vs context_overflow vs fatal)
- Context compression for overflow errors
- Graceful fallback generation from partial results
- Smart retry counting (non-retryable errors don't waste attempts)
'''

from __future__ import annotations

import logging

from agent.config import MAX_RETRIES, PROVIDER_DEFAULT, VERSION
from agent.dependencies import AgentDeps
from agent.session_globals import close_db
from agent.healing import (
    SelfHealingRunner,
    ErrorClassifier,
    FallbackHandler,
)

logger = logging.getLogger(__name__)

AUTO_REPAIR_TASK_PREFIX = "[Auto-repair]"
_MAX_REPAIR_PARTIAL_LEN = 3000


def _build_repair_goal(
    original_task: str,
    last_error: str,
    partial_output: str | None,
    attempt_count: int,
) -> str:
    """Build goal for a resumable auto-repair task with full error context."""
    partial = (partial_output or "").strip()
    if len(partial) > _MAX_REPAIR_PARTIAL_LEN:
        partial = partial[: _MAX_REPAIR_PARTIAL_LEN] + "\n... [truncated]"
    return (
        f"{AUTO_REPAIR_TASK_PREFIX} The previous run failed after {attempt_count} attempt(s). "
        "Fix the cause and complete the original task. Use get_todo if needed, then reply with the result.\n\n"
        f"Original goal:\n{original_task}\n\n"
        f"Last error:\n{last_error}\n\n"
        + (f"Partial output before failure:\n{partial}\n\n" if partial else "")
        + "Fix the error and complete or report progress."
    )


def _should_create_repair_task(task: str, deps: AgentDeps | None) -> bool:
    """True if we are in a bot chat and this task is not already an auto-repair."""
    if deps is None or deps.chat_id == 0:
        return False
    return not task.strip().startswith(AUTO_REPAIR_TASK_PREFIX)


async def run_with_retry(
    task: str,
    max_retries: int | None = None,
    chat_id: int = 0,
    deps: AgentDeps | None = None,
    provider: str | None = None,
    resumable_task_id: int | None = None,
) -> str:
    """Run agent task with session support and self-healing retries.

    This is the core runner function that handles:
    - Intelligent error classification
    - Context compression for overflow errors
    - Graceful fallback generation
    - Smart retry counting (non-retryable errors don't waste attempts)
    
    Args:
        task: Initial task description.
        max_retries: Override config (default: MAX_RETRIES from config).
        chat_id: Chat ID for session isolation (default: 0 for CLI).
        deps: Pre-created dependencies (optional, will create if not provided).
        provider: 'vllm' or 'openrouter' (default: from config).

    Returns:
        Agent output as a string. On failure: meaningful fallback with partial results.
    """
    # --- Special built‑in tasks ------------------------------------------------
    # Accept both "status" and commands like "run status".
    cleaned = task.strip().lower()
    if cleaned == "status" or cleaned.startswith("run ") and cleaned.endswith(" status"):
        # Provide a concise status string without invoking LLM or session DB.
        tools = (
            "shell, filesystem, web_search, todo, backup, run_tests, "
            "run_agent_subprocess, git, request_restart, memory"
        )
        status_msg = (
            f"Agent status: idle (v{VERSION})\n"
            f"Default provider: {PROVIDER_DEFAULT}\n"
            f"Available tools: {tools}\n"
            "Session support: SQLite (data/sessions.db)"
        )
        return status_msg

    from agent.core.agent import build_session_agent

    n = max_retries if max_retries is not None else MAX_RETRIES
    # Create dependencies if not provided
    if deps is None:
        deps = await AgentDeps.create(chat_id=chat_id)

    # Log user message to session
    await deps.add_user_message(task)

    # Build agent
    agent = build_session_agent(provider=provider)

    # Create self-healing runner
    healing_runner = SelfHealingRunner(max_retries=n)

    try:
        # Run with self-healing
        result, success = await healing_runner.run(
            agent=agent,
            task=task,
            deps=deps,
            max_retries=n,
        )

        # Record the assistant's reply in the session history for continuity.
        if success:
            # Successful run – store the final output
            output_text = getattr(result, "output", None) if not isinstance(result, str) else result
            await deps.add_assistant_message(output_text)
            if resumable_task_id is not None:
                await deps.db.mark_resumable_task_completed(resumable_task_id)
            logger.info("Task completed successfully")
            return output_text
        else:
            # Fallback case – store whatever partial output exists, if any
            if isinstance(result, str):
                output_text = result
            elif hasattr(result, "output"):
                output_text = result.output
            else:
                output_text = str(result)
            await deps.add_assistant_message(output_text)
            if resumable_task_id is not None:
                await deps.db.mark_resumable_task_failed(resumable_task_id, "Fallback after retries")
            if _should_create_repair_task(task, deps):
                last_err = getattr(deps, "last_error", None) or "Fallback after retries"
                attempt_count = getattr(deps, "retry_count", None) or n
                repair_goal = _build_repair_goal(task, last_err, output_text, attempt_count)
                await deps.db.upsert_resumable_task(deps.session_id, deps.chat_id, repair_goal)
                logger.info("Created auto-repair resumable task for chat_id=%s", deps.chat_id)
            return output_text
    except Exception as e:
        # Last-resort error handling
        logger.error(f"Unexpected error in runner: {e}")
        if resumable_task_id is not None and deps is not None:
            await deps.db.mark_resumable_task_failed(resumable_task_id, str(e))
        if _should_create_repair_task(task, deps):
            attempt_count = getattr(deps, "retry_count", None) or 1
            repair_goal = _build_repair_goal(task, str(e), None, attempt_count)
            await deps.db.upsert_resumable_task(deps.session_id, deps.chat_id, repair_goal)
            logger.info("Created auto-repair resumable task for chat_id=%s after exception", deps.chat_id)
        fallback = FallbackHandler()
        return fallback.generate_from_error(e, attempt_count=1)


async def run_task_with_session(
    task: str,
    chat_id: int,
    username: str | None = None,
    user_id: int | None = None,
    session_scope: str = "main",
    provider: str | None = None,
    resumable_task_id: int | None = None,
) -> str:
    """Run a task with full session management.

    This is the preferred entry point for running agent tasks with
    SQLite session persistence and memory support.

    OpenClaw-inspired architecture:
    - Sessions are isolated per chat_id and scope
    - Conversation history is persisted in SQLite
    - Memory (L0/L1/L2) is available across sessions
    - User context is preserved for personalization
    """
    deps = await AgentDeps.create(
        chat_id=chat_id,
        username=username,
        user_id=user_id,
        session_scope=session_scope,
    )

    return await run_with_retry(
        task, deps=deps, provider=provider, resumable_task_id=resumable_task_id
    )


async def run_simple_task(task: str, model_name: str | None = None, provider: str | None = None) -> str:
    """Run a simple task without session persistence.
    \n    Useful for one‑off tasks that don't need session isolation\n    or memory persistence.
    """
    from agent.core.agent import build_agent

    agent = build_agent(model_name=model_name, provider=provider)
    
    try:
        result = await agent.run(task)
        return getattr(result, "output", str(result))
    except Exception as e:
        logger.error(f"Simple task failed: {e}")
        fallback = FallbackHandler()
        return fallback.generate_from_error(e, attempt_count=1)


async def cleanup():
    """Cleanup resources on application shutdown.
    \n    Closes the database connection and any other resources.
    Should be called when the application is shutting down.
    """
    await close_db()
    logger.info("Runner cleanup completed")

# ============ Legacy Support ============

async def run_with_retry_legacy(
    task: str,
    max_retries: int | None = None,
    chat_id: int = 0,
    deps: AgentDeps | None = None,
    provider: str | None = None,
) -> str:
    """Legacy runner without self‑healing (for comparison/testing).
    \n    This is the original implementation that counts all errors\n    against retry limit, even non‑retryable ones.
    """
    from agent.core.agent import build_session_agent

    n = max_retries if max_retries is not None else MAX_RETRIES
    current_task = task
    last_error: Exception | None = None
    agent = build_session_agent(provider=provider)

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
                await deps.add_assistant_message(getattr(result, "output", str(result)))

                logger.info(f"Task completed successfully")
                return getattr(result, "output", str(result))

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
        await deps.add_assistant_message(msg)
        return msg
    except Exception as e:
        logger.error(f"Unexpected error in legacy runner: {e}")
        fallback = FallbackHandler()
        return fallback.generate_from_error(e, attempt_count=1)
