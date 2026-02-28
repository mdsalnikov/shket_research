"""Progress tracking for transparent agent work monitoring.

This module provides real-time progress tracking for agent tasks,
sending updates to both Telegram bot and CLI users.

Features:
- Track TODO list changes
- Send progress updates on each step
- Show current activity in real-time
- Support for both Telegram and CLI interfaces
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class ProgressState(Enum):
    """States for progress tracking."""

    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class ProgressUpdate:
    """Progress update message."""

    timestamp: float = field(default_factory=time.time)
    state: ProgressState = ProgressState.IDLE
    step_number: int = 0
    total_steps: int = 0
    current_task: str = ""
    todo_count: int = 0
    completed_count: int = 0
    message: str = ""
    details: dict = field(default_factory=dict)

    def to_string(self) -> str:
        """Convert to human-readable string."""
        state_emoji = {
            ProgressState.IDLE: "⏸️",
            ProgressState.PLANNING: "📝",
            ProgressState.EXECUTING: "⚙️",
            ProgressState.COMPLETED: "✅",
            ProgressState.FAILED: "❌",
        }

        emoji = state_emoji.get(self.state, "📌")
        progress = f"{self.completed_count}/{self.todo_count}" if self.todo_count > 0 else "N/A"

        lines = [
            f"{emoji} **Progress Update**",
            f"State: {self.state.name}",
            f"Progress: {progress}",
        ]

        if self.current_task:
            lines.append(f"Current: {self.current_task}")

        if self.message:
            lines.append(f"Message: {self.message}")

        return "\n".join(lines)


class ProgressTracker:
    """Tracks agent progress and sends updates to subscribers.

    Usage:
        tracker = ProgressTracker(chat_id=123, is_cli=False)
        tracker.start_task("My task")
        tracker.update_todo(5, 2, "Current step description")
        tracker.set_state(ProgressState.EXECUTING, "Processing data...")
        tracker.complete()
    """

    def __init__(
        self,
        chat_id: int = 0,
        is_cli: bool = True,
        telegram_callback: Callable[[int, str], Awaitable[None]] | None = None,
        cli_callback: Callable[[str], None] | None = None,
    ):
        """Initialize progress tracker.

        Args:
            chat_id: Telegram chat ID (0 for CLI)
            is_cli: True if running in CLI mode
            telegram_callback: Async function(chat_id, message) for Telegram updates
            cli_callback: Function(message) for CLI output
        """
        self.chat_id = chat_id
        self.is_cli = is_cli
        self.telegram_callback = telegram_callback
        self.cli_callback = cli_callback

        self.state = ProgressState.IDLE
        self.task_name = ""
        self.current_task = ""  # Track current task description
        self.todo_items: list[str] = []
        self.completed_items: list[str] = []
        self.current_step = 0
        self.total_steps = 0
        self.completed_count = 0  # Track completed steps
        self.start_time: float | None = None
        self.end_time: float | None = None

        self._lock = asyncio.Lock()
        self._update_counter = 0

    async def start_task(self, task_name: str) -> None:
        """Start tracking a new task.

        Args:
            task_name: Name/description of the task
        """
        async with self._lock:
            self.task_name = task_name
            self.state = ProgressState.PLANNING
            self.start_time = time.time()
            self._update_counter = 0
            self.completed_count = 0

            await self._send_update(
                state=ProgressState.PLANNING,
                message=f"Starting task: {task_name}",
            )

    async def update_todo(
        self,
        total_steps: int,
        completed_count: int,
        current_task: str = "",
    ) -> None:
        """Update TODO list status.

        Args:
            total_steps: Total number of steps in TODO
            completed_count: Number of completed steps
            current_task: Description of current step
        """
        async with self._lock:
            self.total_steps = total_steps
            self.current_step = completed_count
            self.completed_count = completed_count
            self.current_task = current_task

            await self._send_update(
                state=ProgressState.EXECUTING if completed_count > 0 else ProgressState.PLANNING,
                step_number=completed_count,
                total_steps=total_steps,
                current_task=current_task,
                todo_count=total_steps,
                completed_count=completed_count,
                message=f"Step {completed_count}/{total_steps} completed"
                if completed_count > 0
                else "Planning complete",
            )

    async def set_state(self, state: ProgressState, message: str = "") -> None:
        """Set current state with optional message.

        Args:
            state: New state
            message: Optional description
        """
        async with self._lock:
            self.state = state

            await self._send_update(
                state=state,
                message=message,
                current_task=self.current_task,
                todo_count=self.total_steps,
                completed_count=self.completed_count,
            )

    async def on_step_start(self, step_number: int, step_description: str) -> None:
        """Called when a step starts.

        Args:
            step_number: Step number (1-based)
            step_description: Description of the step
        """
        await self._send_update(
            state=ProgressState.EXECUTING,
            step_number=step_number,
            total_steps=self.total_steps,
            current_task=step_description,
            todo_count=self.total_steps,
            completed_count=step_number - 1,
            message=f"🔄 Starting step {step_number}: {step_description}",
        )

    async def on_step_complete(
        self, step_number: int, step_description: str, result: str = ""
    ) -> None:
        """Called when a step completes.

        Args:
            step_number: Step number (1-based)
            step_description: Description of the step
            result: Optional result summary
        """
        await self._send_update(
            state=ProgressState.EXECUTING,
            step_number=step_number,
            total_steps=self.total_steps,
            current_task=step_description,
            todo_count=self.total_steps,
            completed_count=step_number,
            message=f"✅ Step {step_number} completed: {step_description}"
            + (f" - {result}" if result else ""),
        )

    async def complete(self, final_message: str = "") -> None:
        """Mark task as completed.

        Args:
            final_message: Optional completion message
        """
        async with self._lock:
            self.state = ProgressState.COMPLETED
            self.end_time = time.time()

            duration = self.end_time - self.start_time if self.start_time else 0
            duration_str = self._format_duration(duration)

            message = final_message or "Task completed successfully"
            if duration_str:
                message += f" (Duration: {duration_str})"

            await self._send_update(
                state=ProgressState.COMPLETED,
                message=message,
                todo_count=self.total_steps,
                completed_count=self.total_steps,
            )

    async def fail(self, error_message: str) -> None:
        """Mark task as failed.

        Args:
            error_message: Error description
        """
        async with self._lock:
            self.state = ProgressState.FAILED
            self.end_time = time.time()

            await self._send_update(
                state=ProgressState.FAILED,
                message=f"❌ Task failed: {error_message}",
                todo_count=self.total_steps,
                completed_count=self.completed_count,
            )

    async def _send_update(self, **update_params) -> None:
        """Send progress update to subscribers.

        Args:
            **update_params: Parameters for ProgressUpdate
        """
        self._update_counter += 1

        update = ProgressUpdate(**update_params)
        message = update.to_string()

        # Send to appropriate interface
        if self.is_cli:
            await self._send_cli_update(message, update)
        elif self.telegram_callback:
            await self._send_telegram_update(message)

    async def _send_cli_update(self, message: str, update: ProgressUpdate) -> None:
        """Send update to CLI.

        Args:
            message: Formatted message
            update: ProgressUpdate object
        """
        # Print with timestamp and progress bar
        timestamp = time.strftime("%H:%M:%S", time.localtime(update.timestamp))

        # Create progress bar
        if update.total_steps > 0:
            filled = "=" * update.completed_count
            empty = "-" * (update.total_steps - update.completed_count)
            bar = f"[{filled}{empty}]"
        else:
            bar = "[N/A]"

        output = f"\n[{timestamp}] {bar} {message}"

        if self.cli_callback:
            self.cli_callback(output)
        else:
            print(output)

    async def _send_telegram_update(self, message: str) -> None:
        """Send update to Telegram.

        Args:
            message: Formatted message
        """
        if self.telegram_callback and self.chat_id:
            try:
                await self.telegram_callback(self.chat_id, message)
            except Exception as e:
                logger.error("Failed to send Telegram update: %s", e)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable form.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string (e.g., "2m 30s")
        """
        if seconds < 60:
            return f"{int(seconds)}s"

        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)

        if minutes < 60:
            return f"{minutes}m {remaining_seconds}s"

        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m"

    def get_status(self) -> dict:
        """Get current status as dictionary.

        Returns:
            Dictionary with current status information
        """
        duration = 0
        if self.end_time and self.start_time:
            duration = self.end_time - self.start_time
        elif self.start_time:
            duration = time.time() - self.start_time

        return {
            "task": self.task_name,
            "state": self.state.name,
            "progress": f"{self.completed_count}/{self.total_steps}"
            if self.total_steps > 0
            else "N/A",
            "duration": self._format_duration(duration),
            "updates": self._update_counter,
        }


# Global tracker instances (one per chat_id for Telegram, one for CLI)
_trackers: dict[int, ProgressTracker] = {}


def get_tracker(chat_id: int = 0, is_cli: bool = True) -> ProgressTracker:
    """Get or create progress tracker for a chat.

    Args:
        chat_id: Chat ID (0 for CLI)
        is_cli: True if CLI mode

    Returns:
        ProgressTracker instance
    """
    key = chat_id if not is_cli else 0

    if key not in _trackers:
        _trackers[key] = ProgressTracker(
            chat_id=chat_id,
            is_cli=is_cli,
        )

    return _trackers[key]


def reset_tracker(chat_id: int = 0, is_cli: bool = True) -> None:
    """Reset tracker for a chat.

    Args:
        chat_id: Chat ID (0 for CLI)
        is_cli: True if CLI mode
    """
    key = chat_id if not is_cli else 0

    if key in _trackers:
        del _trackers[key]
