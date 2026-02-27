"""Self-test tools: backup, run tests, run agent in subprocess without killing current instance."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time

logger = logging.getLogger(__name__)

WORKSPACE = "/workspace"
VENV_PYTHON = os.path.join(WORKSPACE, ".venv", "bin", "python")
TIMEOUT_TESTS = 120
TIMEOUT_AGENT = 90


async def backup_codebase() -> str:
    """Create a full backup of the current codebase before self-modification.

    Use this BEFORE any changes to agent code. Backup is saved to .backup_YYYYMMDD_HHMMSS/.
    """
    logger.info("Tool backup_codebase")
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(WORKSPACE, f".backup_{ts}")
    def _ignore(_d: str, names: list[str]) -> list[str]:
        skip = (".venv", "__pycache__", ".git")
        return [n for n in names if n in skip or n.startswith(".backup_")]

    try:
        shutil.copytree(WORKSPACE, dest, ignore=_ignore, dirs_exist_ok=False)
        return f"Backup created at {dest}"
    except Exception as e:
        return f"error: {e}"


def _python() -> str:
    return VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python"


async def run_tests(test_path: str = "tests/test_cli.py") -> str:
    """Run pytest in a subprocess. Use to verify code changes before applying.

    Args:
        test_path: Test file or directory. Default: tests/test_cli.py (unit tests).
    """
    logger.info("Tool run_tests: %s", test_path)
    cmd = [_python(), "-m", "pytest", test_path, "-v", "--tb=short"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=WORKSPACE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_TESTS)
        out = stdout.decode(errors="replace").strip()
        if len(out) > 6000:
            out = out[:6000] + "\n… (truncated)"
        return f"exit_code={proc.returncode}\n{out}"
    except asyncio.TimeoutError:
        return "error: pytest timed out after 120s"
    except Exception as e:
        return f"error: {e}"


async def run_agent_subprocess(task: str) -> str:
    """Run the agent with a task in a fresh subprocess. Use to test self-modifications.

    The subprocess loads code from disk, so after you change files, this runs the NEW code.
    Never kills the current agent — always runs in a separate process.

    Args:
        task: Task to run (e.g. 'echo hello' or 'run status').
    """
    logger.info("Tool run_agent_subprocess: %s", task[:80])
    cmd = [_python(), "-m", "agent", "run", task]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=WORKSPACE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ},
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_AGENT)
        out = stdout.decode(errors="replace").strip()
        if len(out) > 6000:
            out = out[:6000] + "\n… (truncated)"
        return f"exit_code={proc.returncode}\n{out}"
    except asyncio.TimeoutError:
        return "error: agent subprocess timed out after 90s"
    except Exception as e:
        return f"error: {e}"
