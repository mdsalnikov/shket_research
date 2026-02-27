"""Git tools for committing and pushing self-modifications."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

WORKSPACE = "/workspace"
TIMEOUT = 30


async def _run_git(args: list[str]) -> tuple[int, str]:
    cmd = ["git", "-C", WORKSPACE] + args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
    out = stdout.decode(errors="replace").strip()
    return proc.returncode or 0, out


async def git_status() -> str:
    """Show git status (working tree, staged, branch)."""
    logger.info("Tool git_status")
    code, out = await _run_git(["status", "--short"])
    branch_code, branch_out = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_out.strip() if branch_code == 0 else "?"
    header = f"Branch: {branch}\n\n"
    return header + (out or "Working tree clean")


async def git_add(paths: list[str]) -> str:
    """Stage files for commit. Use '.' to stage all changes.

    Args:
        paths: File paths to stage (relative to workspace). Use ["."] for all.
    """
    logger.info("Tool git_add: %s", paths)
    code, out = await _run_git(["add"] + paths)
    if code != 0:
        return f"error (exit {code}): {out}"
    return f"Staged: {', '.join(paths)}"


async def git_commit(message: str) -> str:
    """Create a commit with the staged changes.

    Args:
        message: Commit message (required).
    """
    logger.info("Tool git_commit: %s", message[:50])
    if not message.strip():
        return "error: commit message cannot be empty"
    code, out = await _run_git(["commit", "-m", message])
    if code != 0:
        return f"error (exit {code}): {out}"
    return f"Committed: {out.split(chr(10))[0] if out else message}"


async def git_push(branch: str | None = None) -> str:
    """Push commits to remote. Uses current branch if branch not specified.

    Args:
        branch: Branch to push. Default: current branch.
    """
    logger.info("Tool git_push: %s", branch or "current")
    args = ["push", "origin", branch] if branch else ["push"]
    code, out = await _run_git(args)
    if code != 0:
        return f"error (exit {code}): {out}"
    return "Pushed successfully"
