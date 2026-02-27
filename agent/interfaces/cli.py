"""CLI interface with session support."""

import argparse
import asyncio
import logging
from pathlib import Path

from agent.config import LOG_FILE, setup_logging
from agent.session_globals import close_db, get_db

logger = logging.getLogger(__name__)

# Read version from VERSION file
VERSION_FILE = Path(__file__).parent.parent.parent / "VERSION"
VERSION = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "unknown"


async def _run_task(task: str) -> None:
    """Run a task with session support (CLI mode uses chat_id=0)."""
    from agent.core.runner import run_with_retry

    try:
        output = await run_with_retry(task, chat_id=0)
        print(output)
    finally:
        await close_db()


async def _show_memory_summary() -> None:
    """Show memory summary."""
    try:
        db = await get_db()
        l0 = await db.get_l0_overview()

        if not l0:
            print("No memories stored.")
            return

        print("=== Memory Summary (L0) ===\n")
        for category, summaries in l0.items():
            print(f"[{category}]")
            for summary in summaries:
                print(f"  - {summary}")
            print()

    finally:
        await close_db()


def _show_logs(n: int) -> None:
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Log file not found: {LOG_FILE}")
        return
    tail = lines[-n:] if len(lines) > n else lines
    print(f"--- last {len(tail)} of {len(lines)} log entries ---")
    print("".join(tail), end="")


def main():
    parser = argparse.ArgumentParser(
        prog="python -m agent",
        description=f"Shket Research Agent v{VERSION} — автономный LLM‑агент для Ubuntu‑сервера",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Выполнить задачу")
    run_p.add_argument("task", help="Описание задачи на естественном языке")

    sub.add_parser("bot", help="Запустить Telegram‑бот (long‑polling)")
    sub.add_parser("status", help="Показать статус агента")
    sub.add_parser("version", help="Показать версию агента")
    sub.add_parser("memory", help="Показать сводку памяти")

    logs_p = sub.add_parser("logs", help="Показать последние записи лога")
    logs_p.add_argument("n", nargs="?", type=int, default=30, help="Количество строк (по умолчанию 30)")

    args = parser.parse_args()

    if args.command == "logs":
        _show_logs(args.n)
        return

    setup_logging()

    if args.command == "run":
        asyncio.run(_run_task(args.task))
    elif args.command == "status":
        print(f"Agent status: idle (v{VERSION})")
        tools = (
            "shell, filesystem, web_search, todo, backup, run_tests, "
            "run_agent_subprocess, git, request_restart, memory"
        )
        print(f"Available tools: {tools}")
        print("Session support: SQLite (data/sessions.db)")
    elif args.command == "version":
        print(f"Shket Research Agent v{VERSION}")
    elif args.command == "memory":
        asyncio.run(_show_memory_summary())
    elif args.command == "bot":
        from agent.interfaces.telegram import run_bot
        run_bot()
    else:
        parser.print_help()
        print(f"\nVersion: {VERSION}")
