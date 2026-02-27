import argparse
import asyncio
import logging

from agent.config import LOG_FILE, setup_logging

logger = logging.getLogger(__name__)


async def _run_task(task: str) -> None:
    from agent.core.agent import build_agent

    agent = build_agent()
    result = await agent.run(task)
    print(result.output)


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
        description="Shket Research Agent — autonomous LLM agent for Ubuntu server",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Execute a task")
    run_p.add_argument("task", help="Task description in natural language")

    sub.add_parser("bot", help="Start the Telegram bot (long-polling)")
    sub.add_parser("status", help="Show agent status")

    logs_p = sub.add_parser("logs", help="Show recent log entries")
    logs_p.add_argument("n", nargs="?", type=int, default=30, help="Number of lines (default 30)")

    args = parser.parse_args()

    if args.command == "logs":
        _show_logs(args.n)
        return

    setup_logging()

    if args.command == "run":
        asyncio.run(_run_task(args.task))
    elif args.command == "status":
        print("Agent status: idle")
        tools = (
            "shell, filesystem, web_search, todo, backup, run_tests, "
            "run_agent_subprocess, git, request_restart"
        )
        print(f"Available tools: {tools}")
    elif args.command == "bot":
        from agent.interfaces.telegram import run_bot

        run_bot()
    else:
        parser.print_help()
