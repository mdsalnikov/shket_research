from __future__ import annotations

import logging
import os

from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)


def _safe_path(path: str) -> str:
    base = os.path.realpath(PROJECT_ROOT)
    resolved = os.path.realpath(os.path.join(base, path))
    if not resolved.startswith(base):
        raise ValueError(f"Path escapes workspace: {path}")
    return resolved


async def read_file(path: str) -> str:
    """Read contents of a file.

    Args:
        path: Relative path from the workspace root.
    """
    logger.info("Tool read_file: %s", path)
    full = _safe_path(path)
    with open(full) as f:
        content = f.read()
    if len(content) > 8000:
        content = content[:8000] + "\n… (truncated)"
    return content


async def write_file(path: str, content: str) -> str:
    """Write content to a file (creates parent dirs if needed).

    Args:
        path: Relative path from the workspace root.
        content: The text content to write.
    """
    logger.info("Tool write_file: %s (%d chars)", path, len(content))
    full = _safe_path(path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return f"Written {len(content)} chars to {path}"


async def list_dir(path: str = ".") -> str:
    """List contents of a directory.

    Args:
        path: Relative path from the workspace root. Defaults to root.
    """
    logger.info("Tool list_dir: %s", path)
    full = _safe_path(path)
    entries = sorted(os.listdir(full))
    return "\n".join(entries)
