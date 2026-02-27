import argparse
import logging

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Shket Research Agent")
    sub = parser.add_subparsers(dest="command")
    run_parser = sub.add_parser("run", help="Run a task")
    run_parser.add_argument("task", help="Task description")
    args = parser.parse_args()

    if args.command == "run":
        logger.info("Received task: %s", args.task)
        print(f"Agent received task: {args.task}")
        print("Agent core not yet implemented — scaffold only.")
    else:
        parser.print_help()
