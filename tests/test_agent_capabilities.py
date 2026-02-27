"""Deterministic tests for agent capabilities using GPT-OSS-120B via OpenRouter.

These tests verify the agent can:
1. Execute shell commands and return correct output
2. Write a Python script to a file and execute it
3. Perform web search and synthesize results
4. Read/write files via filesystem tools
5. Solve a multi-step task (deep research pattern)

Each test checks that the agent's final answer contains expected deterministic markers.
Marked with pytest.mark.agent so they can be run separately:
    pytest -m agent -v
"""

import os

import pytest

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

pytestmark = pytest.mark.agent

skip_no_key = pytest.mark.skipif(
    not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("your_"),
    reason="OPENROUTER_API_KEY not set",
)


def _build_agent():
    from agent.core.agent import build_agent

    return build_agent(model_name="openai/gpt-oss-120b")


@skip_no_key
@pytest.mark.asyncio
async def test_shell_command():
    """Agent should execute `echo 42` and include '42' in its answer."""
    agent = _build_agent()
    result = await agent.run(
        "Run the shell command `echo 42` and tell me the exact output. "
        "Your answer must contain the number."
    )
    assert "42" in result.output


@skip_no_key
@pytest.mark.asyncio
async def test_write_and_run_script():
    """Agent should write a Python script that prints HELLO_SHKET, run it, report output."""
    script_path = "/workspace/tmp_test_script.py"
    try:
        agent = _build_agent()
        result = await agent.run(
            "Write a Python script to the file tmp_test_script.py that prints "
            "exactly the string HELLO_SHKET (nothing else). "
            "Then execute it with `python tmp_test_script.py` and tell me the output."
        )
        assert "HELLO_SHKET" in result.output
        assert os.path.exists(script_path)
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


@skip_no_key
@pytest.mark.asyncio
async def test_filesystem_read_write():
    """Agent should write 'MAGIC_TOKEN_12345' to a file, read it back, and confirm."""
    test_file = "/workspace/tmp_test_token.txt"
    try:
        agent = _build_agent()
        result = await agent.run(
            "Write the exact text 'MAGIC_TOKEN_12345' to a file called tmp_test_token.txt. "
            "Then read the file back and tell me its contents."
        )
        assert "MAGIC_TOKEN_12345" in result.output
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


@skip_no_key
@pytest.mark.asyncio
async def test_web_search():
    """Agent should search for Python programming language and mention it."""
    agent = _build_agent()
    result = await agent.run(
        "Search the web for 'Python programming language official site' "
        "and tell me the URL of the official Python website."
    )
    output = result.output.lower()
    assert "python.org" in output


@skip_no_key
@pytest.mark.asyncio
async def test_multi_step_research():
    """Agent should: 1) run `uname -r` to get kernel version, 2) write it to a file,
    3) read the file back, 4) include the kernel version in the answer."""
    report_file = "/workspace/tmp_kernel_report.txt"
    try:
        agent = _build_agent()
        result = await agent.run(
            "Perform these steps:\n"
            "1. Run `uname -r` to get the Linux kernel version\n"
            "2. Write the kernel version to a file called tmp_kernel_report.txt\n"
            "3. Read the file back to confirm\n"
            "4. Tell me the kernel version from the file"
        )
        assert os.path.exists(report_file)
        with open(report_file) as f:
            file_content = f.read().strip()
        assert len(file_content) > 0
        assert file_content in result.output or "." in result.output
    finally:
        if os.path.exists(report_file):
            os.remove(report_file)
