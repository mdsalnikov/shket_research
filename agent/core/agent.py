from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from agent.config import DEFAULT_MODEL, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Shket Research Agent — an autonomous AI assistant running on an Ubuntu server.

You have access to the following tools:
- run_shell: execute shell commands on the host OS (non-root user)
- read_file / write_file / list_dir: filesystem operations
- web_search: search the web and retrieve information

Rules:
1. Always use tools when the task requires interacting with the OS, files, or the web.
2. For shell commands, prefer simple one-liners. Avoid interactive commands.
3. When writing code/scripts, write them to files using write_file, then execute with run_shell.
4. For research tasks, use web_search to find information, then synthesize a clear answer.
5. Be concise and precise in your final answers.
6. If a task asks you to write a script, always save it to a file AND execute it to verify it works.
"""


def build_model(
    model_name: str | None = None,
    api_key: str | None = None,
) -> OpenRouterModel:
    return OpenRouterModel(
        model_name or DEFAULT_MODEL,
        provider=OpenRouterProvider(api_key=api_key or OPENROUTER_API_KEY),
    )


def build_agent(
    model_name: str | None = None,
    api_key: str | None = None,
) -> Agent:
    model = build_model(model_name, api_key)
    from agent.tools.filesystem import list_dir, read_file, write_file
    from agent.tools.shell import run_shell
    from agent.tools.web import web_search

    agent = Agent(
        model,
        system_prompt=SYSTEM_PROMPT,
        tools=[run_shell, read_file, write_file, list_dir, web_search],
    )
    return agent
