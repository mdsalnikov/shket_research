from __future__ import annotations

import asyncio
import logging

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

TIMEOUT = 30


async def run_shell(command: str) -> str:
    """Execute a shell command on the host OS and return stdout+stderr.

    Args:
        command: The shell command to execute.
    """
    with log_tool_call("run_shell", command) as tool_log:
        logger.info("Tool run_shell: %s", command)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=PROJECT_ROOT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            output = stdout.decode(errors="replace").strip()
            if len(output) > 4000:
                output = output[:4000] + "\n… (truncated)"
            result = f"exit_code={proc.returncode}\n{output}"
        except asyncio.TimeoutError:
            proc.kill()
            result = "error: command timed out after 30s"
        except Exception as e:
            result = f"error: {e}"
        
        tool_log.log_result(f"exit_code={proc.returncode if 'proc' in dir() else '?'}, output_len={len(output) if 'output' in dir() else 0}")
        return result
