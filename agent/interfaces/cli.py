"""CLI interface with session support and progress tracking."""

import argparse
import asyncio
import logging
from pathlib import Path

from agent.config import LOG_FILE, PROVIDER_DEFAULT, setup_logging
from agent.session_globals import close_db, get_db
from agent.progress import get_tracker

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
    
    # Configure progress tracker for CLI
    tracker = get_tracker(chat_id=0, is_cli=True)
    
    # Set up CLI callback for progress updates
    def cli_progress_callback(message: str) -> None:
        """Callback for progress updates in CLI."""
        print(message, flush=True)
    
    tracker.cli_callback = cli_progress_callback
    
    try:
        output = await run_with_retry(task, chat_id=0, provider=provider)
        print("\n" + output)
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


async def _resume_task() -> None:
    """Load one incomplete resumable task, run resume, print result (no Telegram)."""
    from agent.config import PROVIDER_DEFAULT
    from agent.core.runner import run_task_with_session
    from agent.interfaces.telegram import _build_resume_prompt, MAX_RESUME_COUNT
    try:
        db = await get_db()
        incomplete = await db.get_incomplete_resumable_tasks()
        if not incomplete:
            print("No incomplete resumable tasks.")
            await close_db()
            return
        row = incomplete[0]
        if row["resume_count"] >= MAX_RESUME_COUNT:
            await db.mark_resumable_task_failed(row["id"], "Max resume count exceeded")
            print(f"Task {row['id']} exceeded max resume count; marked failed.")
            await close_db()
            return
        await db.increment_resume_and_set_resumed_at(row["id"])
        prompt = _build_resume_prompt(row["goal"], row["resume_count"] + 1)
        print(f"Resuming task {row['id']} (chat_id={row['chat_id']}): {row['goal'][:60]}...")
        try:
            result = await run_task_with_session(
                prompt,
                chat_id=row["chat_id"],
                provider=PROVIDER_DEFAULT,
                resumable_task_id=None,
            )
            await db.mark_resumable_task_completed(row["id"])
            print(result)
        except Exception as e:
            await db.mark_resumable_task_failed(row["id"], str(e))
            print(f"Resume failed: {e}")
    finally:
        await close_db()


async def _long_list(chat_id: int | None = None, limit: int = 20) -> None:
    """Print resumable tasks (optionally for one chat_id)."""
    try:
        db = await get_db()
        tasks = await db.get_resumable_tasks(chat_id=chat_id, limit=limit)
        if not tasks:
            print("No resumable tasks.")
            await close_db()
            return
        print("ID   STATUS      CHAT_ID  RESUME  GOAL (preview)")
        print("-" * 60)
        for t in tasks:
            goal = (t["goal"] or "")[:40] + ("…" if len(t["goal"] or "") > 40 else "")
            print(f"{t['id']:<5} {t['status']:<11} {t['chat_id']:<8} {t.get('resume_count', 0)}      {goal}")
    finally:
        await close_db()


async def _long_show(task_id: int) -> None:
    """Print one resumable task by id."""
    try:
        db = await get_db()
        t = await db.get_resumable_task_by_id(task_id)
        if not t:
            print(f"Task {task_id} not found.")
            await close_db()
            return
        print(f"ID: {t['id']}  status: {t['status']}  chat_id: {t['chat_id']}  resume_count: {t.get('resume_count', 0)}")
        print(f"created_at: {t.get('created_at')}  updated_at: {t.get('updated_at')}")
        if t.get("last_error"):
            print(f"last_error: {t['last_error']}")
        print(f"goal:\n{t['goal']}")
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

    run_parser = sub.add_parser("run", help="Run a task")
    run_parser.add_argument("task", nargs="?", default="", help="Task description")
    run_parser.add_argument("--provider", choices=["vllm", "openrouter"], help="LLM provider")

    sub.add_parser("status", help="Show agent status")
    sub.add_parser("memory", help="Show memory summary")
    sub.add_parser("clear", help="Clear session context")
    sub.add_parser("context", help="Show session context")
    sub.add_parser("resume", help="Resume incomplete task")
    
    long_parser = sub.add_parser("long", help="Long-running commands")
    long_sub = long_parser.add_subparsers(dest="long_cmd")
    long_list_parser = long_sub.add_parser("list", help="List resumable tasks")
    long_list_parser.add_argument("--chat-id", type=int, help="Filter by chat_id")
    long_list_parser.add_argument("--limit", type=int, default=20, help="Max tasks to show")
    long_show_parser = long_sub.add_parser("show", help="Show task details")
    long_show_parser.add_argument("task_id", type=int, help="Task ID")

    logs_parser = sub.add_parser("logs", help="Show log tail")
    logs_parser.add_argument("n", type=int, nargs="?", default=30, help="Number of lines")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "run":
        if not args.task:
            print("Error: Task description required")
            print("Usage: python -m agent run 'your task'")
            return
        asyncio.run(_run_task(args.task, provider=args.provider))
    elif args.command == "status":
        print(_builtin_status())
    elif args.command == "memory":
        asyncio.run(_show_memory_summary())
    elif args.command == "clear":
        asyncio.run(_clear_context())
    elif args.command == "context":
        asyncio.run(_show_context())
    elif args.command == "resume":
        asyncio.run(_resume_task())
    elif args.command == "long":
        if args.long_cmd == "list":
            asyncio.run(_long_list(chat_id=args.chat_id, limit=args.limit))
        elif args.long_cmd == "show":
            asyncio.run(_long_show(args.task_id))
        else:
            long_parser.print_help()
    elif args.command == "logs":
        _show_logs(args.n)
    else:
        parser.print_help()
