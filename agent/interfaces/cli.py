import argparse
import logging

logger = logging.getLogger(__name__)


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

    if args.command == "run":
        logger.info("Received task: %s", args.task)
        print(f"Agent received task: {args.task}")
        print("Agent core not yet implemented — scaffold only.")
    elif args.command == "status":
        print("Agent status: idle")
        print("Agent core: scaffold (not yet implemented)")
        print("Available tools: shell, browser, filesystem")
    elif args.command == "bot":
        from agent.interfaces.telegram import run_bot

        run_bot()
    else:
        parser.print_help()
