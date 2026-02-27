"""CLI interface with session support."""

import argparse
import asyncio
import logging
from pathlib import Path

from agent.config import LOG_FILE, PROVIDER_DEFAULT, setup_logging
from agent.session_globals import close_db, get_db

logger = logging.getLogger(__name__)

# Read version from VERSION file
VERSION_FILE = Path(__file__).parent.parent.parent / "VERSION"
VERSION = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "unknown"

def _builtin_status() -> str:
    """Return a concise status string used by both the `status` sub‑command
    and the `run status` shortcut.

    This avoids sending the literal "status" to the LLM, which previously
    caused validation retries because the model's output did not match the
    expected format. By handling it locally we provide a deterministic
    response.
    """
    return (
        f"Agent status: idle (v{VERSION})\n"
        f"Default provider: {PROVIDER_DEFAULT}\n"
        "Available tools: shell, filesystem, web_search, todo, backup, run_tests, "
        "run_agent_subprocess, git, request_restart, memory\n"
        "Session support: SQLite (data/sessions.db)\n\n"
        "Usage: python -m agent run 'your task' [--provider vllm|openrouter]"
    )

async def _run_task(task: str, provider: str | None = None) -> None:
    """Run a task with session support (CLI mode uses chat_id=0).
    
    Shortcut: if the user asked for the built‑in status we handle it
    locally instead of sending it to the LLM. This prevents the
    ``Exceeded maximum retries`` validation error observed when calling
    ``python -m agent run status``.
    
    Args:
        task: Task description
        provider: 'vllm' or 'openrouter' (default: from config)
    """
    if task.strip().lower() == "status":
        print(_builtin_status())
        await close_db()
        return

    from agent.core.runner import run_with_retry

    try:
        output = await run_with_retry(task, chat_id=0, provider=provider)
        print(output)
    finally:
        await close_db()

async def _show_memory_summary() -> None:
    """Display a summary of the memory store."""
    from agent.memory import MemoryStore
    store = await MemoryStore.get_instance()
    # Print the count of memory entries per category.
    summary = store.summary()
    for category, count in summary.items():
        print(f"{category}: {count} entries")

def _show_logs(num: int = 50) -> None:
    """Print the last `num` lines from the log file."""
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            for line in lines[-num:]:
                print(line, end="")
    except FileNotFoundError:
        print("Log file not found.")

def main():
    parser = argparse.ArgumentParser(description="Shket Research Agent bot")
    subparsers = parser.add_subparsers(dest="command")

    # Sub‑command: run
    parser_run = subparsers.add_parser("run", help="Run a task")
    parser_run.add_argument("task", type=str, help="Task description")
    parser_run.add_argument(
        "--provider",
        type=str,
        choices=["vllm", "openrouter"],
        help="Provider to use (default from config)",
    )

    # Sub‑command: status
    subparsers.add_parser("status", help="Show agent status")

    # Sub‑command: logs
    parser_logs = subparsers.add_parser("logs", help="Show recent logs")
    parser_logs.add_argument("-n", type=int, default=50, help="Number of lines to show")

    # Sub‑command: memory
    subparsers.add_parser("memory", help="Show memory summary")

    args = parser.parse_args()

    # Setup logging according to config.
    setup_logging()

    if args.command == "logs":
        _show_logs(args.n)
        return

    if args.command == "run":
        asyncio.run(_run_task(args.task, args.provider))
    elif args.command == "status":
        print(_builtin_status())
    elif args.command == "memory":
        asyncio.run(_show_memory_summary())

if __name__ == "__main__":
    main()
