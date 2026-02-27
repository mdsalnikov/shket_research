"""Self-test tools: backup, run tests, run agent in subprocess without killing current instance."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
TIMEOUT_TESTS = 120
TIMEOUT_AGENT = 90
TIMEOUT_BACKUP = 60
MAX_OUTPUT_LEN = 6000

_BACKUP_IGNORE = (".venv", "__pycache__", ".git", "logs")
MAX_BACKUPS = 5


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


def _list_backup_dirs() -> list[str]:
    """Return sorted list of .backup_* dir names in PROJECT_ROOT (newest last)."""
    if not os.path.isdir(PROJECT_ROOT):
        return []
    names = [
        n for n in os.listdir(PROJECT_ROOT)
        if n.startswith(".backup_") and os.path.isdir(os.path.join(PROJECT_ROOT, n))
    ]
    return sorted(names)


def _prune_old_backups() -> None:
    """Keep at most MAX_BACKUPS backups; remove oldest."""
    backups = _list_backup_dirs()
    while len(backups) > MAX_BACKUPS:
        oldest = os.path.join(PROJECT_ROOT, backups[0])
        shutil.rmtree(oldest, ignore_errors=True)
        logger.info("Pruned old backup: %s", backups[0])
        backups = _list_backup_dirs()


async def backup_codebase() -> str:
    """Create a full backup of the current codebase before self-modification.

    Use this BEFORE any changes to agent code. Backup is saved to .backup_YYYYMMDD_HHMMSS/.
    Keeps at most {0} backups; oldest are removed. Runs with 60s timeout.
    """.format(MAX_BACKUPS)
    with log_tool_call("backup_codebase") as tool_log:
        logger.info("Tool backup_codebase")
        ts = time.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(PROJECT_ROOT, f".backup_{ts}")

        def _do_backup() -> None:
            shutil.copytree(PROJECT_ROOT, dest, ignore=_ignore_backup, dirs_exist_ok=False)

        try:
            await asyncio.wait_for(asyncio.to_thread(_do_backup), timeout=TIMEOUT_BACKUP)
            await asyncio.to_thread(_prune_old_backups)
            tool_log.log_result(f"backup at {dest}")
            return f"Backup created at {dest}"
        except asyncio.TimeoutError:
            if os.path.exists(dest):
                shutil.rmtree(dest, ignore_errors=True)
            tool_log.log_result("timeout")
            return f"error: backup timed out after {TIMEOUT_BACKUP}s"
        except Exception as e:
            tool_log.log_result(f"error: {e}")
            return f"error: {e}"


async def list_backups() -> str:
    """List available backup directories (from backup_codebase).

    Returns a list of .backup_YYYYMMDD_HHMMSS dirs, newest last.
    Use with restore_from_backup to rollback after a failed self-modification.
    """
    with log_tool_call("list_backups") as tool_log:
        backups = _list_backup_dirs()
        if not backups:
            tool_log.log_result("0 backups")
            return "No backups found. Run backup_codebase() before self-modification."
        tool_log.log_result(f"{len(backups)} backups")
        return "Available backups (oldest first):\n" + "\n".join(backups)


async def restore_from_backup(backup_dir: str) -> str:
    """Restore the codebase from a backup directory. Use when self-modification failed.

    Overwrites current code with the backup. Does not touch .git or .venv.
    Run this if tests or run_agent_subprocess failed after you edited files.

    Args:
        backup_dir: Name of the backup dir, e.g. .backup_20260228_120000
    """
    with log_tool_call("restore_from_backup", backup_dir) as tool_log:
        logger.info("Tool restore_from_backup: %s", backup_dir)
        base = os.path.realpath(PROJECT_ROOT)
        src_dir = os.path.realpath(os.path.join(base, backup_dir.strip()))
        valid = (
            src_dir.startswith(base)
            and os.path.isdir(src_dir)
            and os.path.basename(src_dir).startswith(".backup_")
        )
        if not valid:
            tool_log.log_result("error: invalid or missing backup dir")
            return f"error: not a .backup_ directory in project: {backup_dir}"

        def _do_restore() -> None:
            for name in os.listdir(src_dir):
                src = os.path.join(src_dir, name)
                dest = os.path.join(base, name)
                if os.path.isdir(src):
                    if os.path.exists(dest):
                        shutil.rmtree(dest)
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)

        try:
            await asyncio.wait_for(asyncio.to_thread(_do_restore), timeout=TIMEOUT_BACKUP)
            tool_log.log_result("restored")
            return f"Restored codebase from {backup_dir}. Re-run tests to confirm."
        except asyncio.TimeoutError:
            tool_log.log_result("timeout")
            return f"error: restore timed out after {TIMEOUT_BACKUP}s"
        except Exception as e:
            tool_log.log_result(f"error: {e}")
            return f"error: {e}"


async def run_tests(test_path: str = "tests/test_cli.py") -> str:
    """Run pytest in a subprocess. Use to verify code changes before applying.

    For self-modification: run at least tests/test_cli.py; for agent/session code
    also run tests/test_session.py or tests/ for the full suite.

    Args:
        test_path: Test file or directory. Default: tests/test_cli.py (unit tests).
    """
    with log_tool_call("run_tests", test_path) as tool_log:
        logger.info("Tool run_tests: %s", test_path)
        cmd = [_python(), "-m", "pytest", test_path, "-v", "--tb=short"]
        try:
            code, out = await _run_subprocess(cmd, TIMEOUT_TESTS)
            tool_log.log_result(f"exit={code}")
            return f"exit_code={code}\n{out}"
        except asyncio.TimeoutError:
            tool_log.log_result("timeout")
            return "error: pytest timed out after 120s"
        except Exception as e:
            tool_log.log_result(f"error: {e}")
            return f"error: {e}"


async def run_agent_subprocess(task: str) -> str:
    """Run the agent with a task in a fresh subprocess. Use to test self-modifications.

    The subprocess loads code from disk, so after you change files, this runs the NEW code.
    Never kills the current agent — always runs in a separate process.
    For self-modification verification use a real agent task, e.g. 'run status' (not 'echo hello').

    Args:
        task: Task to run (e.g. 'run status' or 'list files in .').
    """
    with log_tool_call("run_agent_subprocess", task[:50]) as tool_log:
        logger.info("Tool run_agent_subprocess: %s", task[:80])
        # Determine appropriate command based on requested task.
        # If the user asks for the CLI status command (e.g., "run status"),
        # we invoke the status subcommand directly to avoid unnecessary LLM calls.
        task_clean = task.strip()
        if task_clean == "run status":
            cmd = [_python(), "-m", "agent", "status"]
        elif task_clean.startswith("run "):
            # Run a natural‑language task via the agent's "run" entry point.
            actual_task = task_clean[4:].strip()
            cmd = [_python(), "-m", "agent", "run", actual_task]
        else:
            # Directly invoke any other subcommand (e.g., "status", "memory").
            cmd = [_python(), "-m", "agent", task_clean]
        try:
            code, out = await _run_subprocess(cmd, TIMEOUT_AGENT)
            tool_log.log_result(f"exit={code}")
            return f"exit_code={code}\n{out}"
        except asyncio.TimeoutError:
            tool_log.log_result("timeout")
            return "error: agent subprocess timed out after 90s"
        except Exception as e:
            tool_log.log_result(f"error: {e}")
            return f"error: {e}"
