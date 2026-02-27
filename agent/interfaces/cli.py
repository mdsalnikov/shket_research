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


async def _run_task(task: str, provider: str | None = None) -> None:
    """Run a task with session support (CLI mode uses chat_id=0).
    
    Args:
        task: Task description
        provider: 'vllm' or 'openrouter' (default: from config)
        
    """
    from agent.core.runner import run_with_retry

    try:
        output = await run_with_retry(task, chat_id=0, provider=provider)
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


async def _clear_context() -> None:
    """Clear session context (CLI uses chat_id=0)."""
    try:
        db = await get_db()
        session_id = await db.get_or_create_session(0)  # CLI uses chat_id=0
        await db.clear_session(session_id)
        print("✅ Context cleared successfully!")
        print("   Session metadata preserved, messages deleted.")
    finally:
        await close_db()


async def _show_context() -> None:
    """Show current session context info (CLI uses chat_id=0)."""
    from datetime import datetime
    
    try:
        db = await get_db()
        session_id = await db.get_or_create_session(0)  # CLI uses chat_id=0
        stats = await db.get_session_stats(session_id, include_last_messages=5)
        
        if "error" in stats:
            print(f"Error: {stats['error']}")
            return
        
        print("=== Session Context ===\n")
        print(f"📝 Messages: {stats['message_count']}")
        print(f"🔤 Estimated tokens: {stats['estimated_tokens']:,}")
        print(f"📏 Total chars: {stats['total_chars']:,}")
        print(f"\n⏱ Session created: {stats['created_at']}")
        print(f"🕐 Last activity: {stats['updated_at']}")
        
        uptime_h = int(stats["uptime_seconds"] // 3600)
        uptime_m = int((stats["uptime_seconds"] % 3600) // 60)
        print(f"   Session age: {uptime_h}h {uptime_m}m")
        
        idle_m = int(stats["idle_seconds"] // 60)
        print(f"   Idle: {idle_m}m ago")
        
        if stats["last_messages"]:
            print(f"\n--- Last {len(stats['last_messages'])} messages ---")
            for msg in stats["last_messages"]:
                role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}.get(msg["role"], "📄")
                print(f"\n{role_emoji} [{msg['role']}] ({msg['chars']} chars)")
                print(f"   {msg['content_preview']}")

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
    run_p.add_argument(
        "--provider", "-p",
        choices=["vllm", "openrouter"],
        default=None,
        help=f"LLM provider (default: {PROVIDER_DEFAULT}). Use 'vllm' for local, 'openrouter' for cloud.",
    )

    sub.add_parser("bot", help="Запустить Telegram‑бот (long‑polling)")
    sub.add_parser("status", help="Показать статус агента")
    sub.add_parser("version", help="Показать версию агента")
    sub.add_parser("memory", help="Показать сводку памяти")
    sub.add_parser("context", help="Показать информацию о контексте сессии")
    sub.add_parser("clear-context", help="Очистить контекст сессии (удалить сообщения)")

    logs_p = sub.add_parser("logs", help="Показать последние записи лога")
    logs_p.add_argument("n", nargs="?", type=int, default=30, help="Количество строк (по умолчанию 30)")

    args = parser.parse_args()

    if args.command == "logs":
        _show_logs(args.n)
        return

    setup_logging()

    if args.command == "run":
        asyncio.run(_run_task(args.task, args.provider))
    elif args.command == "status":
        print(f"Agent status: idle (v{VERSION})")
        print(f"Default provider: {PROVIDER_DEFAULT}")
        tools = (
            "shell, filesystem, web_search, todo, backup, run_tests, "
            "run_agent_subprocess, git, request_restart, memory"
        )
        print(f"Available tools: {tools}")
        print("Session support: SQLite (data/sessions.db)")
        print("\nUsage: python -m agent run 'your task' [--provider vllm|openrouter]")
    elif args.command == "version":
        print(f"Shket Research Agent v{VERSION}")
    elif args.command == "memory":
        asyncio.run(_show_memory_summary())
    elif args.command == "context":
        asyncio.run(_show_context())
    elif args.command == "clear-context":
        asyncio.run(_clear_context())
    elif args.command == "bot":
        from agent.interfaces.telegram import run_bot
        run_bot()
    else:
        parser.print_help()
        print(f"\nVersion: {VERSION}")
        print(f"Default provider: {PROVIDER_DEFAULT}")
