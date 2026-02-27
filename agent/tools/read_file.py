"""Read file tool wrapper.

This module provides a thin wrapper around the `read_file` implementation
found in `agent.tools.filesystem`. The agent's tool loading logic expects a
module named `read_file.py` exporting an `async def read_file` function.
"""

from __future__ import annotations

from .filesystem import read_file as _read_file

async def read_file(path: str) -> str:
    """Delegate to the filesystem implementation.

    Args:
        path: Relative path from the workspace root.
    """
    return await _read_file(path)
