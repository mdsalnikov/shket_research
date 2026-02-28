"""Scheduled self-repair: check logs, run agent to fix, merge PR, restart.

Designed to run from cron every hour. Set RESTART_CMD env to restart the bot/service after merge.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from agent.config import BOT_ERRORS_LOG, PROJECT_ROOT
from agent.session_globals import close_db

logger = logging.getLogger(__name__)

SELF_REPAIR_BRANCH_PREFIX = "agent-self-repair-"


def need_self_repair() -> bool:
    """True if bot error log has content (tracebacks) that warrant a repair run."""
    path = Path(BOT_ERRORS_LOG)
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.strip():
        return False
    # Require something that looks like a traceback or exception
    if "Traceback" in text or "Error:" in text or "Exception" in text or "File \"" in text:
        return True
    return False


def _current_branch() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip()
    except Exception as e:
        logger.warning("Could not get current branch: %s", e)
    return None


def _merge_pr_for_branch(branch: str) -> bool:
    """Merge the PR for the given branch. Returns True if merge succeeded."""
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--json", "number", "--jq", ".[0].number"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0 or not out.stdout or out.stdout.strip() == "":
            logger.warning("No PR found for branch %s", branch)
            return False
        pr_num = out.stdout.strip()
        merge_out = subprocess.run(
            ["gh", "pr", "merge", pr_num, "--squash"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if merge_out.returncode != 0:
            logger.warning("gh pr merge failed: %s", merge_out.stderr)
            return False
        return True
    except Exception as e:
        logger.warning("Merge failed: %s", e)
        return False


def _checkout_main_and_pull() -> bool:
    try:
        for cmd in [["git", "checkout", "main"], ["git", "pull", "origin", "main"]]:
            r = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                logger.warning("Git command failed: %s %s", cmd, r.stderr)
                return False
        return True
    except Exception as e:
        logger.warning("Checkout/pull failed: %s", e)
        return False


def merge_pr_and_restart(restart_cmd: str | None = None) -> bool:
    """If current branch is agent-self-repair-*, merge its PR, checkout main, pull, optionally run restart_cmd. Returns True if merge+pull (and restart if provided) succeeded."""
    branch = _current_branch()
    if not branch or not branch.startswith(SELF_REPAIR_BRANCH_PREFIX):
        logger.info("Current branch is not a self-repair branch: %s", branch)
        return False
    if not _merge_pr_for_branch(branch):
        return False
    if not _checkout_main_and_pull():
        return False
    if restart_cmd and restart_cmd.strip():
        try:
            subprocess.run(restart_cmd, shell=True, cwd=PROJECT_ROOT, timeout=60)
            logger.info("Restart command executed")
        except Exception as e:
            logger.warning("Restart command failed: %s", e)
            return False
    return True


def _build_scheduled_task(branch_name: str) -> str:
    return f"""Scheduled self-repair (cron). Do the following in order.

1. Call get_recent_bot_errors(100). If the log is empty or contains no real tracebacks/code errors, reply with exactly: "No repair needed" and do nothing else.
2. If there are real errors (tracebacks, File "...", line X):
   a) backup_codebase()
   b) Fix the reported file and line(s). Minimal change only.
   c) run_tests("tests/test_cli.py") and run_agent_subprocess("run status"). If tests fail, fix or reply with failure.
   d) Create branch exactly: {branch_name}
   e) git_add(["."]), git_commit("self-repair: fix errors from logs (cron)")
   f) git_push("{branch_name}")
   g) run_gh("pr create --title 'Self-repair: fix errors from logs' --body 'Automated fix from hourly cron.'")
   h) Reply with: "Self-repair done. Branch: {branch_name}. PR created. Do not merge — cron will merge and restart."
3. If you replied "No repair needed", the cron script will do nothing else. If you created a PR, the cron script will merge it and restart the service."""


async def run_scheduled_self_repair(provider: str | None = None) -> str:
    """Run the agent with the scheduled self-repair task. Returns agent output."""
    from agent.core.runner import run_with_retry

    branch_name = SELF_REPAIR_BRANCH_PREFIX + datetime.utcnow().strftime("%Y%m%d-%H%M")
    task = _build_scheduled_task(branch_name)
    try:
        output = await run_with_retry(task, chat_id=0, provider=provider)
        return output if isinstance(output, str) else str(output)
    finally:
        await close_db()


def run_self_repair_check(dry_run: bool = False, provider: str | None = None) -> int:
    """Check if self-repair is needed; if yes, run agent, then merge PR and restart (unless dry_run). Returns exit code 0 if nothing to do or all steps ok, 1 on failure."""
    if not need_self_repair():
        print("No self-repair needed (no errors in bot error log).")
        return 0

    print("Self-repair needed: errors found in logs. Running agent...")
    output = asyncio.run(run_scheduled_self_repair(provider=provider))
    print(output)

    if "No repair needed" in output:
        print("Agent reported no repair needed. Exit 0.")
        return 0

    if dry_run:
        print("Dry-run: skipping merge and restart.")
        return 0

    branch = _current_branch()
    if not branch or not branch.startswith(SELF_REPAIR_BRANCH_PREFIX):
        print("No self-repair branch to merge (agent reported no repair or failed). Exit 0.")
        return 0

    restart_cmd = os.getenv("RESTART_CMD", "").strip()
    if merge_pr_and_restart(restart_cmd=restart_cmd or None):
        print("Merged PR, pulled main. Restart command run if set.")
        return 0
    print("Merge or restart failed. Exit 1.")
    return 1
