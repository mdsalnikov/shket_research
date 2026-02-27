"""Self-test tools: backup, run tests, run agent in subprocess without killing current instance."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time

from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
TIMEOUT_TESTS = 120
TIMEOUT_AGENT = 90
TIMEOUT_BACKUP = 60
MAX_OUTPUT_LEN = 6000

_BACKUP_IGNORE = (".venv", "__pycache__", ".git", "logs")


def _ignore_backup(_d: str, names: list[str]) -> list[str]:
    return [n for n in names if n in _BACKUP_IGNORE or n.startswith(".backup_")]


def _python() -> str:
    return VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python"


async def _run_subprocess(cmd: list[str], timeout: int, env: dict | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env or os.environ,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    out = stdout.decode(errors="replace").strip()
    if len(out) > MAX_OUTPUT_LEN:
        out = out[:MAX_OUTPUT_LEN] + "\n… (truncated)"
    return proc.returncode if proc.returncode is not None else -1, out


async def backup_codebase() -> str:
    """Create a full backup of the current codebase before self-modification.

    Use this BEFORE any changes to agent code. Backup is saved to .backup_YYYYMMDD_HHMMSS/.
    Runs with 60s timeout to avoid hanging.
    """
    logger.info("Tool backup_codebase")
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(PROJECT_ROOT, f".backup_{ts}")

    def _do_backup() -> None:
        shutil.copytree(PROJECT_ROOT, dest, ignore=_ignore_backup, dirs_exist_ok=False)

    try:
        await asyncio.wait_for(asyncio.to_thread(_do_backup), timeout=TIMEOUT_BACKUP)
        return f"Backup created at {dest}"
    except asyncio.TimeoutError:
        if os.path.exists(dest):
            shutil.rmtree(dest, ignore_errors=True)
        return f"error: backup timed out after {TIMEOUT_BACKUP}s"
    except Exception as e:
        return f"error: {e}"


async def run_tests(test_path: str = "tests/test_cli.py") -> str:
    """Run pytest in a subprocess. Use to verify code changes before applying.

    Args:
        test_path: Test file or directory. Default: tests/test_cli.py (unit tests).
    """
    logger.info("Tool run_tests: %s", test_path)
    cmd = [_python(), "-m", "pytest", test_path, "-v", "--tb=short"]
    try:
        code, out = await _run_subprocess(cmd, TIMEOUT_TESTS)
        return f"exit_code={code}\n{out}"
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
        code, out = await _run_subprocess(cmd, TIMEOUT_AGENT)
        return f"exit_code={code}\n{out}"
    except asyncio.TimeoutError:
        return "error: agent subprocess timed out after 90s"
    except Exception as e:
        return f"error: {e}"
