"""GitHub CLI tools — use gh with GH_TOKEN from GHTOKEN.txt or env."""

from __future__ import annotations

import asyncio
import logging
import os

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

TIMEOUT = 60


def _gh_env() -> dict:
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


async def run_gh(args: str) -> str:
    """Run gh CLI with GH_TOKEN from GHTOKEN.txt or GH_TOKEN env.

    Args:
        args: gh command and args, e.g. "pr list" or "repo view".
    """
    with log_tool_call("run_gh", args[:60]) as tool_log:
        logger.info("Tool run_gh: %s", args[:80])
        cmd = ["gh"] + args.split()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=PROJECT_ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=_gh_env(),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            out = stdout.decode(errors="replace").strip()
            if len(out) > 6000:
                out = out[:6000] + "\n… (truncated)"
            result = f"exit_code={proc.returncode or 0}\n{out}"
            tool_log.log_result(f"exit={proc.returncode or 0}, {len(out)} chars")
            return result
        except asyncio.TimeoutError:
            tool_log.log_result("timeout")
            return "error: gh timed out after 60s"
        except Exception as e:
            tool_log.log_result(f"error: {e}")
            return f"error: {e}"
