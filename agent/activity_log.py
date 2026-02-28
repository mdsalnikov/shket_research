"""Human-readable activity logging for agent actions.

This module provides a separate log that shows what the agent is doing
in a format that's easy for users to understand.

Format example:
  2026-02-27 20:09:00 | 👤 USER: сделай что-то
  2026-02-27 20:09:01 | 🔧 run_shell: ls -la
  2026-02-27 20:09:02 | ✅ run_shell → exit_code=0 (0.5s)
  2026-02-27 20:09:03 | 🤖 AGENT: готово
"""

import functools
import os
import time
from datetime import datetime
from typing import Any, Callable

from agent.config import BOT_ERRORS_LOG, PROJECT_ROOT

ACTIVITY_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "activity.log")

# Ensure log directory exists
os.makedirs(os.path.dirname(ACTIVITY_LOG_FILE), exist_ok=True)


def _timestamp() -> str:
    """Return current timestamp in readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _truncate(text: str, max_len: int = 500) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def log_user_message(chat_id: int, text: str) -> None:
    """Log incoming user message."""
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{_timestamp()} | 👤 USER ({chat_id}): {_truncate(text)}\n")


def log_agent_response(chat_id: int, text: str) -> None:
    """Log outgoing agent response."""
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{_timestamp()} | 🤖 AGENT → {chat_id}: {_truncate(text)}\n")


def log_task_start(task_id: int, text: str) -> None:
    """Log task start."""
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{_timestamp()} | 🚀 TASK #{task_id} START: {_truncate(text, 200)}\n")


def log_task_end(task_id: int, success: bool, duration: float, error: str | None = None) -> None:
    """Log task completion."""
    status = "✅" if success else "❌"
    duration_str = f"{duration:.1f}s"
    msg = f"{_timestamp()} | {status} TASK #{task_id} END ({duration_str})"
    if error:
        msg += f" ERROR: {_truncate(error, 200)}"
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


class ToolCallLogger:
    """Context manager for logging tool calls with timing."""

    def __init__(self, tool_name: str, params: dict | str | None = None):
        self.tool_name = tool_name
        self.params = params
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        params_str = ""
        if self.params:
            if isinstance(self.params, dict):
                # Increase per-param truncation to 300 chars for better visibility
                params_str = " | " + ", ".join(
                    f"{k}={_truncate(str(v), 300)}" for k, v in self.params.items()
                )
            else:
                # Show up to 2000 characters of raw params
                params_str = f" | {_truncate(str(self.params), 2000)}"
        with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{_timestamp()} | 🔧 {self.tool_name}{params_str}\n")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{_timestamp()} | ❌ {self.tool_name} → ERROR: "
                    f"{_truncate(str(exc_val), 2000)} ({duration:.2f}s)\n"
                )
        return False  # Don't suppress exceptions

    def log_result(self, result: str) -> None:
        """Log successful result."""
        duration = time.time() - self.start_time
        # Show up to 3000 characters of result for detailed debugging
        with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{_timestamp()} | ✅ {self.tool_name} → "
                f"{_truncate(result, 3000)} ({duration:.2f}s)\n"
            )


def log_tool_call(tool_name: str | None = None, context: str | None = None):
    """Decorator or context manager for logging tool calls with timing.

    Context manager: with log_tool_call("tool_name", "param detail") as tool_log:
    Decorator: @log_tool_call or @log_tool_call("custom_name")
    """
    if context is not None:
        return ToolCallLogger(tool_name or "tool", context)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Use provided name or function name
            name = tool_name if tool_name else func.__name__

            # Prepare params string
            params = {}
            if args:
                # Get parameter names from function signature
                import inspect

                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        params[param_names[i]] = arg
            params.update(kwargs)

            params_str = (
                ", ".join(f"{k}={_truncate(str(v), 300)}" for k, v in params.items())
                if params
                else None
            )

            with ToolCallLogger(name, params_str) as logger:
                try:
                    result = func(*args, **kwargs)
                    logger.log_result(_truncate(str(result), 3000))
                    return result
                except Exception:
                    raise

        return wrapper

    # If called without parentheses (e.g., @log_tool_call), tool_name will be the function
    if callable(tool_name):
        func = tool_name
        tool_name = None
        return decorator(func)

    # Single string arg: support both "with log_tool_call('name')" and "@log_tool_call('name')"
    if tool_name is not None:

        class _Dual:
            def __enter__(self):
                self._logger = ToolCallLogger(tool_name, None)
                return self._logger.__enter__()

            def __exit__(self, *args):
                return self._logger.__exit__(*args)

            def __call__(self, func: Callable) -> Callable:
                return decorator(func)

        return _Dual()

    return decorator


def log_error(context: str, error: str) -> None:
    """Log an error."""
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{_timestamp()} | ⚠️ ERROR | {context}: {_truncate(error, 300)}\n")


def get_activity_log_tail(n: int = 50) -> str:
    """Get last n lines of activity log."""
    try:
        with open(ACTIVITY_LOG_FILE, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "📝 Activity log is empty (no actions yet)"

    tail = lines[-n:] if len(lines) > n else lines
    header = f"📝 Last {len(tail)} of {len(lines)} entries:\n\n"
    return header + "".join(tail)


def get_bot_errors_tail(n: int = 50) -> str:
    """Get last n lines of Telegram bot error log (for self-repair)."""
    try:
        with open(BOT_ERRORS_LOG, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "No bot errors logged yet."

    tail = lines[-n:] if len(lines) > n else lines
    return "".join(tail)
