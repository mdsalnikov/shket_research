"""Tests for git tools."""

import os

import pytest

from agent.tools.git import git_add, git_status


@pytest.mark.asyncio
async def test_git_status():
    """git_status returns branch and status."""
    out = await git_status()
    assert "Branch:" in out or "branch" in out.lower()
    assert isinstance(out, str)
    assert len(out) > 0


@pytest.mark.asyncio
async def test_git_add():
    """git_add stages a file."""
    test_file = "/workspace/tmp_git_test_add.txt"
    with open(test_file, "w") as f:
        f.write("test")
    try:
        out = await git_add(["tmp_git_test_add.txt"])
        assert "Staged" in out or "error" not in out.lower()
    finally:
        os.remove(test_file)
        import subprocess

        subprocess.run(
            ["git", "-C", "/workspace", "restore", "--staged", "tmp_git_test_add.txt"],
            capture_output=True,
        )
