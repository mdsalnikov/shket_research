import subprocess
import sys


def test_agent_status():
    result = subprocess.run(
        [sys.executable, "-m", "agent", "status"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Available tools" in result.stdout
    assert "Default provider" in result.stdout


def test_agent_help():
    result = subprocess.run(
        [sys.executable, "-m", "agent", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "bot" in result.stdout
    assert "status" in result.stdout


def test_run_help_shows_provider():
    result = subprocess.run(
        [sys.executable, "-m", "agent", "run", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--provider" in result.stdout or "-p" in result.stdout
    assert "vllm" in result.stdout or "openrouter" in result.stdout
