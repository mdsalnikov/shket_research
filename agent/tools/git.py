"""Git tools for committing and pushing self-modifications.

Uses gh CLI for GitHub authentication (no SSH required).
"""

from __future__ import annotations

import asyncio
import logging
import os

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

TIMEOUT = 60


def _gh_token_env() -> dict:
    """Return env with GH_TOKEN from GHTOKEN.txt or env if available."""
    env = dict(os.environ)
    token = env.get("GH_TOKEN")
    if not token:
        for path in ("GHTOKEN.txt", ".gh_token"):
            full = os.path.join(PROJECT_ROOT, path)
            if os.path.exists(full):
                with open(full) as f:
                    token = f.read().strip()
                break
    if token:
        env["GH_TOKEN"] = token
    return env


async def _run_gh_auth_setup() -> tuple[int, str]:
    """Run 'gh auth setup-git' to configure git to use gh as credential helper."""
    env = _gh_token_env()
    proc = await asyncio.create_subprocess_exec(
        "gh",
        "auth",
        "setup-git",
        cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    out = stdout.decode(errors="replace").strip()
    return proc.returncode or 0, out


async def _run_git(args: list[str]) -> tuple[int, str]:
    """Run git command with gh authentication configured."""
    cmd = ["git", "-C", PROJECT_ROOT] + args
    env = _gh_token_env()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
    out = stdout.decode(errors="replace").strip()
    return proc.returncode or 0, out


async def git_status() -> str:
    """Show git status (working tree, staged, branch)."""
    with log_tool_call("git_status") as tool_log:
        logger.info("Tool git_status")
        code, out = await _run_git(["status", "--short"])
        branch_code, branch_out = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_out.strip() if branch_code == 0 else "?"
        header = f"Branch: {branch}\n\n"
        result = header + (out or "Working tree clean")
        tool_log.log_result(f"branch={branch}, {len(out.split(chr(10)))} lines")
        return result


async def git_add(paths: list[str]) -> str:
    """Stage files for commit. Use '.' to stage all changes.

    Args:
        paths: File paths to stage (relative to workspace). Use ["."] for all.
    """
    with log_tool_call("git_add", ", ".join(paths)) as tool_log:
        logger.info("Tool git_add: %s", paths)
        code, out = await _run_git(["add"] + paths)
        if code != 0:
            tool_log.log_result(f"error (exit {code})")
            return f"error (exit {code}): {out}"
        tool_log.log_result(f"staged {len(paths)} paths")
        return f"Staged: {', '.join(paths)}"


async def git_commit(message: str) -> str:
    """Create a commit with the staged changes.

    Args:
        message: Commit message (required).
    """
    with log_tool_call("git_commit", message[:50]) as tool_log:
        logger.info("Tool git_commit: %s", message[:50])
        if not message.strip():
            tool_log.log_result("error: empty message")
            return "error: commit message cannot be empty"
        code, out = await _run_git(["commit", "-m", message])
        if code != 0:
            tool_log.log_result(f"error (exit {code})")
            return f"error (exit {code}): {out}"
        tool_log.log_result("committed")
        return f"Committed: {out.split(chr(10))[0] if out else message}"


async def git_pull(branch: str = "main") -> str:
    """Pull latest from remote. Uses gh CLI for authentication.

    Args:
        branch: Branch to pull.
    """
    with log_tool_call("git_pull", branch) as tool_log:
        logger.info("Tool git_pull: %s", branch)
        # Ensure gh credential helper is configured for authentication
        await _run_gh_auth_setup()
        code, out = await _run_git(["pull", "origin", branch])
        if code != 0:
            tool_log.log_result(f"error (exit {code})")
            return f"error (exit {code}): {out}"
        tool_log.log_result("pulled")
        return f"Pulled {branch} successfully"


async def git_checkout(branch: str) -> str:
    """Switch to branch.

    Args:
        branch: Branch name (e.g. main).
    """
    with log_tool_call("git_checkout", branch) as tool_log:
        logger.info("Tool git_checkout: %s", branch)
        code, out = await _run_git(["checkout", branch])
        if code != 0:
            tool_log.log_result(f"error (exit {code})")
            return f"error (exit {code}): {out}"
        tool_log.log_result(f"switched to {branch}")
        return f"Switched to {branch}"


async def git_push(branch: str | None = None) -> str:
    """Push commits to remote. Uses gh CLI for authentication.

    This function uses 'gh auth setup-git' to configure git to use gh CLI
    as a credential helper, allowing push without SSH keys.

    Args:
        branch: Branch to push. Default: current branch.
    """
    with log_tool_call("git_push", branch or "current") as tool_log:
        logger.info("Tool git_push: %s", branch or "current")

        # Ensure gh credential helper is configured for authentication
        auth_code, auth_out = await _run_gh_auth_setup()
        if auth_code != 0:
            logger.warning("gh auth setup-git returned: %s", auth_out)

        # Now push using gh credential helper for authentication
        args = ["push", "origin", branch] if branch else ["push", "origin", "HEAD"]
        code, out = await _run_git(args)
        if code != 0:
            tool_log.log_result(f"error (exit {code})")
            return f"error (exit {code}): {out}"
        tool_log.log_result("pushed")
        return "Pushed successfully"
