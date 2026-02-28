"""Agent task runner with session support and self-healing retries.

This module provides the main entry points for running agent tasks
with SQLite session persistence (OpenClaw-inspired architecture) and
intelligent self-healing error recovery.

Self-healing features:
- Error classification (recoverable vs context_overflow vs fatal)
- Context compression for overflow errors
- Graceful fallback generation from partial results
- Smart retry counting (non-retryable errors don't waste attempts)

Progress tracking:
- Real-time TODO updates
- Progress notifications to Telegram/CLI
- Step-by-step activity reporting
"""

from __future__ import annotations

import logging

from agent.config import MAX_RETRIES, PROVIDER_DEFAULT, VERSION
from agent.dependencies import AgentDeps
from agent.healing import (
    FallbackHandler,
    SelfHealingRunner,
)
from agent.progress import get_tracker

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
        partial = partial[:_MAX_REPAIR_PARTIAL_LEN] + "\n... [truncated]"
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
    agent = await build_session_agent(provider=provider)

    # Create self-healing runner
    healing_runner = SelfHealingRunner(max_retries=n)

    # Initialize progress tracker
    is_cli = chat_id == 0
    tracker = get_tracker(chat_id=chat_id, is_cli=is_cli)

    try:
        # Start progress tracking
        await tracker.start_task(task)

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

            # Mark progress as complete
            await tracker.complete("Task completed successfully")

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
                await deps.db.mark_resumable_task_failed(
                    resumable_task_id, "Fallback after retries"
                )

            # Mark progress as failed
            await tracker.fail("Fallback after retries")

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

        # Mark progress as failed
        await tracker.fail(str(e))

        if resumable_task_id is not None and deps is not None:
            await deps.db.mark_resumable_task_failed(resumable_task_id, str(e))
        if _should_create_repair_task(task, deps):
            attempt_count = getattr(deps, "retry_count", None) or 1
            repair_goal = _build_repair_goal(task, str(e), None, attempt_count)
            await deps.db.upsert_resumable_task(deps.session_id, deps.chat_id, repair_goal)
            logger.info(
                "Created auto-repair resumable task for chat_id=%s after exception", deps.chat_id
            )
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


async def run_simple_task(
    task: str, model_name: str | None = None, provider: str | None = None
) -> str:
    """Run a simple task without session persistence.

    Useful for one‑off tasks that don't need session isolation
    or memory persistence.

    Args:
        task: Task description
        model_name: Model name override
        provider: 'vllm' or 'openrouter'

    Returns:
        Agent output as string
    """
    from agent.core.agent import build_simple_agent

    agent = build_simple_agent(provider=provider)

    # Initialize progress tracker for CLI
    tracker = get_tracker(chat_id=0, is_cli=True)

    try:
        await tracker.start_task(task)
        result = await agent.run(task)
        await tracker.complete()
        return result.output
    except Exception as e:
        await tracker.fail(str(e))
        raise
