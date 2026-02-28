"""Self-healing strategies and main runner integration.

Orchestrates error classification, context compression, and fallback
generation for intelligent error recovery.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from pydantic_ai import ModelMessagesTypeAdapter

from agent.healing.classifier import (
    ClassifiedError,
    ErrorClassifier,
    ErrorType,
)
from agent.healing.compressor import ContextCompressor, compress_session_history
from agent.healing.fallback import (
    FallbackHandler,
    create_fallback_from_session,
)

logger = logging.getLogger(__name__)

# Max message history entries to pass to the model (avoids context overflow)
MAX_MESSAGE_HISTORY = 40


async def _load_message_history(deps: Any) -> list | None:
    """Load pydantic-ai message history for context continuity. Returns None if empty."""
    if not hasattr(deps, "get_model_message_history"):
        return None
    try:
        raw = await deps.get_model_message_history()
        if not raw or not raw.strip():
            return None
        history = ModelMessagesTypeAdapter.validate_json(raw)
        if not history:
            return None
        if len(history) > MAX_MESSAGE_HISTORY:
            return history[-MAX_MESSAGE_HISTORY:]
        return history
    except Exception as e:
        logger.debug("Could not load message history: %s", e)
        return None


async def _save_message_history(deps: Any, result: Any, previous: list | None) -> None:
    """Append run's new messages to stored history and persist."""
    if not hasattr(deps, "set_model_message_history"):
        return
    try:
        new_msgs = result.new_messages()
        if not new_msgs:
            return
        full = (previous or []) + list(new_msgs)
        if len(full) > MAX_MESSAGE_HISTORY:
            full = full[-MAX_MESSAGE_HISTORY:]
        json_bytes = ModelMessagesTypeAdapter.dump_json(full)
        await deps.set_model_message_history(json_bytes.decode("utf-8"))
    except Exception as e:
        logger.warning("Could not save message history: %s", e)


class HealingAction(Enum):
    """Actions the healing system can take."""

    RETRY = auto()  # Simple retry
    COMPRESS_AND_RETRY = auto()  # Compress context then retry
    WAIT_AND_RETRY = auto()  # Wait before retry
    FALLBACK = auto()  # Give up, return fallback
    ABORT = auto()  # Immediately abort (no retry possible)


@dataclass
class HealingResult:
    """Result of healing attempt.

    Attributes:
        action: Action taken
        success: Whether healing succeeded
        message: Status message
        compressed_history: Compressed history (if applicable)
        wait_seconds: Wait time (if applicable)

    """

    action: HealingAction
    success: bool
    message: str
    compressed_history: list[dict[str, Any]] | None = None
    wait_seconds: int | None = None


@dataclass
class CapturedRun:
    """Captured run state for history preservation.

    Stores messages exchanged during a run, even if it crashes.
    Used to preserve partial results for fallback generation.

    Attributes:
        user_messages: List of user messages
        assistant_messages: List of assistant messages
        tool_calls: List of tool call records
        last_error: Last error that occurred (if any)
        attempt_count: Number of attempts made

    """

    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None
    attempt_count: int = 0


@asynccontextmanager
async def capture_run_messages(deps: Any):
    """Context manager that captures run messages even on crash.

    Ensures that conversation history is preserved even when
    agent execution fails. This allows fallback generation
    to use partial results.

    Args:
        deps: AgentDeps instance

    Yields:
        CapturedRun instance to track messages

    Example:
        async with capture_run_messages(deps) as captured:
            result = await agent.run(task, deps=deps)
            captured.assistant_messages.append(result.output)

        # Even if exception occurs, captured has partial history

    """
    captured = CapturedRun()

    try:
        # Get existing history from deps
        if hasattr(deps, "get_conversation_history"):
            try:
                history = await deps.get_conversation_history(limit=50)
                for msg in history:
                    if msg.get("role") == "user":
                        captured.user_messages.append(str(msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        captured.assistant_messages.append(str(msg.get("content", "")))
                    elif msg.get("role") == "tool":
                        captured.tool_calls.append(msg)
            except Exception as e:
                logger.debug(f"Could not load history: {e}")

        yield captured

    except Exception as e:
        # Capture error before re-raising
        captured.last_error = str(e)
        logger.error(f"Run failed with error: {e}")
        raise

    finally:
        # Ensure messages are stored in deps for fallback
        try:
            # Store captured messages in deps for later use
            if hasattr(deps, "_captured_run"):
                deps._captured_run = captured

            # Try to persist any uncommitted messages
            if captured.assistant_messages and hasattr(deps, "add_assistant_message"):
                # Only add if not already in session
                try:
                    last_assistant = captured.assistant_messages[-1]
                    if last_assistant:
                        # This might fail if session is closed, that's OK
                        await deps.add_assistant_message(last_assistant)
                except Exception as e:
                    logger.debug(f"Could not save final assistant message: {e}")
        except Exception as e:
            logger.warning(f"Could not finalize captured messages: {e}")


class HealingStrategy:
    """Determines healing strategy based on error classification.

    Maps error types to appropriate healing actions and manages
    the healing process.

    Example:
        strategy = HealingStrategy()
        action = strategy.determine_action(classified_error)
        result = await strategy.execute(action, deps, error)

    """

    def __init__(
        self,
        max_retries: int = 3,
        max_wait_seconds: int = 60,
    ):
        """Initialize healing strategy.

        Args:
            max_retries: Maximum retries for recoverable errors
            max_wait_seconds: Maximum wait time for rate limits

        """
        self.max_retries = max_retries
        self.max_wait_seconds = max_wait_seconds
        self.classifier = ErrorClassifier()
        self.compressor = ContextCompressor()
        self.fallback = FallbackHandler()

    def determine_action(
        self,
        classified: ClassifiedError,
        attempt: int,
        max_attempts: int,
    ) -> HealingAction:
        """Determine appropriate healing action.

        Args:
            classified: Classified error
            attempt: Current attempt number (0-indexed)
            max_attempts: Maximum attempts

        Returns:
            HealingAction to take

        """
        # If we've exhausted retries, fallback
        if attempt >= max_attempts - 1:
            return HealingAction.FALLBACK

        # Map error type to action
        action_map = {
            ErrorType.CONTEXT_OVERFLOW: HealingAction.COMPRESS_AND_RETRY,
            ErrorType.RATE_LIMIT: HealingAction.WAIT_AND_RETRY,
            ErrorType.USAGE_LIMIT: HealingAction.ABORT,
            ErrorType.AUTH_ERROR: HealingAction.ABORT,
            ErrorType.FATAL: HealingAction.FALLBACK,
            ErrorType.RECOVERABLE: HealingAction.RETRY,
            ErrorType.UNKNOWN: HealingAction.RETRY,
        }

        return action_map.get(classified.error_type, HealingAction.RETRY)

    async def execute(
        self,
        action: HealingAction,
        deps: Any,
        error: Exception,
        attempt: int,
        max_attempts: int,
    ) -> HealingResult:
        """Execute healing action.

        Args:
            action: Action to execute
            deps: AgentDeps instance
            error: The exception that occurred
            attempt: Current attempt number
            max_attempts: Maximum attempts

        Returns:
            HealingResult with outcome

        """
        classified = self.classifier.classify(error)

        if action == HealingAction.RETRY:
            return HealingResult(
                action=action,
                success=True,
                message="Retrying with error context",
            )

        elif action == HealingAction.COMPRESS_AND_RETRY:
            try:
                result = await compress_session_history(deps, target_messages=10)
                return HealingResult(
                    action=action,
                    success=True,
                    message=f"Compressed context (removed {result.removed_count} messages)",
                    compressed_history=result.compressed_history,
                )
            except Exception as e:
                logger.error(f"Context compression failed: {e}")
                return HealingResult(
                    action=HealingAction.FALLBACK,
                    success=False,
                    message=f"Compression failed: {e}",
                )

        elif action == HealingAction.WAIT_AND_RETRY:
            wait_seconds = classified.metadata.get("wait_seconds", 30)
            wait_seconds = min(wait_seconds, self.max_wait_seconds)

            logger.info(f"Rate limited, waiting {wait_seconds}s...")
            await asyncio.sleep(wait_seconds)

            return HealingResult(
                action=action,
                success=True,
                message=f"Waited {wait_seconds}s, ready to retry",
                wait_seconds=wait_seconds,
            )

        elif action == HealingAction.ABORT:
            return HealingResult(
                action=action,
                success=False,
                message="Non-retryable error, aborting",
            )

        elif action == HealingAction.FALLBACK:
            return HealingResult(
                action=action,
                success=False,
                message="Generating fallback response",
            )

        # Default: retry
        return HealingResult(
            action=HealingAction.RETRY,
            success=True,
            message="Unknown action, defaulting to retry",
        )


class SelfHealingRunner:
    """Main self-healing runner that wraps agent execution.

    Integrates with run_with_retry to provide intelligent error recovery:
    1. Classify errors to determine if retry makes sense
    2. Apply appropriate healing strategy (compress/wait/fallback)
    3. Generate meaningful responses even on failure
    4. Track attempts only for retryable errors
    5. Preserve history even on crash via capture_run_messages

    Example:
        runner = SelfHealingRunner()
        result = await runner.run(
            agent=agent,
            task="analyze files",
            deps=deps,
            max_retries=5,
        )

    """

    def __init__(self, max_retries: int | None = None):
        """Initialize self-healing runner.

        Args:
            max_retries: Override max retries (uses config if None)

        """
        from agent.config import MAX_RETRIES

        self.max_retries = max_retries or MAX_RETRIES
        self.strategy = HealingStrategy(max_retries=self.max_retries)
        self.classifier = ErrorClassifier()
        self.fallback = FallbackHandler()

        # Track actual retry attempts (only for retryable errors)
        self._retryable_attempts = 0
        self._total_attempts = 0

    def should_count_as_retry(self, error: Exception) -> bool:
        """Check if error should count against retry limit.

        Non-retryable errors (USAGE_LIMIT, AUTH_ERROR) don't waste retries.

        Args:
            error: The exception that occurred

        Returns:
            True if this should count as a retry attempt

        """
        classified = self.classifier.classify(error)
        return classified.is_retryable

    async def run(
        self,
        agent: Any,
        task: str,
        deps: Any,
        max_retries: int | None = None,
    ) -> tuple[str, bool]:
        """Run agent with self-healing.

        Uses capture_run_messages to preserve history even on crash.

        Args:
            agent: Agent instance with .run() method
            task: Task description
            deps: AgentDeps instance
            max_retries: Override max retries

        Returns:
            Tuple of (response, success)

        """
        n = max_retries or self.max_retries
        current_task = task
        last_error: Exception | None = None
        last_classified: ClassifiedError | None = None

        # Reset attempt counters
        self._retryable_attempts = 0
        self._total_attempts = 0

        # Use capture_run_messages to preserve history even on crash
        async with capture_run_messages(deps) as captured:
            for attempt in range(n):
                self._total_attempts += 1
                captured.attempt_count = attempt + 1

                try:
                    logger.info(f"Running task (attempt {attempt + 1}/{n})")
                    message_history = await _load_message_history(deps)
                    result = await agent.run(
                        current_task,
                        deps=deps,
                        message_history=message_history,
                    )
                    await _save_message_history(deps, result, message_history)
                    await deps.add_assistant_message(result.output)
                    captured.assistant_messages.append(result.output)
                    logger.info("Task completed successfully")
                    return result.output, True

                except Exception as e:
                    last_error = e
                    last_classified = self.classifier.classify(e)

                    logger.warning(f"Attempt {attempt + 1}/{n} failed: {e}")
                    deps.last_error = str(e)
                    captured.last_error = str(e)

                    # Determine if this counts as a retry
                    if self.should_count_as_retry(e):
                        self._retryable_attempts += 1
                        deps.retry_count = self._retryable_attempts
                    else:
                        # Non-retryable error - don't count it
                        logger.info(f"Non-retryable error: {last_classified.error_type.name}")

                    # Determine healing action
                    action = self.strategy.determine_action(last_classified, attempt, n)

                    # Execute healing action
                    healing_result = await self.strategy.execute(action, deps, e, attempt, n)

                    if not healing_result.success:
                        # Healing failed, generate fallback
                        if action == HealingAction.ABORT:
                            # Immediate abort - don't waste retries
                            fallback = await create_fallback_from_session(deps, e, attempt + 1)
                            return fallback, False

                        # Generate fallback and return
                        fallback = await create_fallback_from_session(deps, e, attempt + 1)
                        return fallback, False

                    # Prepare for retry
                    if action == HealingAction.COMPRESS_AND_RETRY:
                        # Context was compressed, use compressed history
                        if healing_result.compressed_history:
                            # Add compression note to task
                            current_task = self.fallback.generate_retry_prompt(task, e, attempt, n)
                            # Store compressed history for next attempt
                            deps._compressed_history = healing_result.compressed_history

                    elif action == HealingAction.WAIT_AND_RETRY:
                        # Already waited, prepare retry prompt
                        current_task = self.fallback.generate_retry_prompt(task, e, attempt, n)

                    elif action == HealingAction.RETRY:
                        # Simple retry with error context
                        current_task = self.fallback.generate_retry_prompt(task, e, attempt, n)

                    else:
                        # Fallback action
                        fallback = await create_fallback_from_session(deps, e, attempt + 1)
                        return fallback, False

            # Exhausted all attempts
            fallback = (
                await create_fallback_from_session(deps, last_error, n)
                if last_error
                else "Task failed without error"
            )

            return fallback, False

    def get_stats(self) -> dict[str, int]:
        """Get healing statistics.

        Returns:
            Dict with attempt counts

        """
        return {
            "total_attempts": self._total_attempts,
            "retryable_attempts": self._retryable_attempts,
        }
