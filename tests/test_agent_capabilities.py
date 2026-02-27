"""Agent capability tests via vLLM (local) or OpenRouter.

Tests verify: shell, filesystem, web search, multi-step tasks.
Run with vLLM (localhost): USE_VLLM=1 pytest tests/test_agent_capabilities.py -v
Run with OpenRouter: pytest -m agent -v (requires OPENROUTER_API_KEY)
"""

import os

import pytest

from agent.config import PROJECT_ROOT

USE_VLLM = os.getenv("USE_VLLM", "").lower() in ("1", "true", "yes")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TEST_MODEL = os.getenv("AGENT_TEST_MODEL", "openai/gpt-oss-120b")

pytestmark = pytest.mark.agent

skip_no_backend = pytest.mark.skipif(
    not USE_VLLM and (not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("your_")),
    reason="Set USE_VLLM=1 for local vLLM or OPENROUTER_API_KEY for OpenRouter",
)


def _build_agent():
    from agent.core.agent import build_agent

    if USE_VLLM:
        return build_agent(provider="vllm")
    return build_agent(model_name=TEST_MODEL)


@skip_no_backend
@pytest.mark.asyncio
async def test_shell_command():
    """Agent should execute `echo 42` and include '42' in its answer."""
    agent = _build_agent()
    result = await agent.run(
        "Run the shell command `echo 42` and tell me the exact output. "
        "Your answer must contain the number."
    )
    assert "42" in result.output


@skip_no_backend
@pytest.mark.asyncio
async def test_write_and_run_script():
    """Agent should write a Python script that prints HELLO_SHKET, run it, report output."""
    script_path = os.path.join(PROJECT_ROOT, "tmp_test_script.py")
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


@skip_no_backend
@pytest.mark.asyncio
async def test_filesystem_read_write():
    """Agent should write 'MAGIC_TOKEN_12345' to a file, read it back, and confirm."""
    test_file = os.path.join(PROJECT_ROOT, "tmp_test_token.txt")
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


@skip_no_backend
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


@skip_no_backend
@pytest.mark.asyncio
async def test_git_status():
    """Agent should run git_status and include branch or status in the answer."""
    agent = _build_agent()
    result = await agent.run(
        "Run git_status and tell me the current branch or status."
    )
    output = result.output.lower()
    assert "branch" in output or "clean" in output or "modified" in output


@skip_no_backend
@pytest.mark.asyncio
async def test_multi_step_research():
    """Agent should: 1) run `uname -r` to get kernel version, 2) write it to a file,
    3) read the file back, 4) include the kernel version in the answer."""
    report_file = os.path.join(PROJECT_ROOT, "tmp_kernel_report.txt")
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


@skip_no_backend
@pytest.mark.asyncio
async def test_message_history_continuity():
    """With session, second run should see context from first (message_history passed)."""
    from agent.core.runner import run_with_retry
    from agent.session_globals import close_db

    try:
        r1 = await run_with_retry("Reply with exactly: CONTEXT_OK", chat_id=99999, provider="vllm")
        assert "CONTEXT_OK" in r1
        r2 = await run_with_retry(
            "Your previous reply was about CONTEXT. Say exactly: CONTINUITY_OK",
            chat_id=99999,
            provider="vllm",
        )
        assert "CONTINUITY_OK" in r2
    finally:
        await close_db()
