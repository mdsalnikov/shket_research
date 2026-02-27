import subprocess
import sys


def test_agent_run_hello_world():
    result = subprocess.run(
        [sys.executable, "-m", "agent", "run", "hello world"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Agent received task: hello world" in result.stdout


def test_agent_no_args():
    result = subprocess.run(
        [sys.executable, "-m", "agent"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
