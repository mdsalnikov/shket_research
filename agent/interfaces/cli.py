import argparse
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _run_task(task: str) -> None:
    from agent.core.agent import build_agent

    agent = build_agent()
    result = await agent.run(task)
    print(result.output)


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

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    if args.command == "run":
        asyncio.run(_run_task(args.task))
    elif args.command == "status":
        print("Agent status: idle")
        print("Available tools: shell, browser, filesystem, web_search")
    elif args.command == "bot":
        from agent.interfaces.telegram import run_bot

        run_bot()
    else:
        parser.print_help()
