from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from agent.config import DEFAULT_MODEL, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Shket Research Agent — an autonomous AI assistant running on an Ubuntu server.

Tools:
- run_shell: execute shell commands on the host OS (non-root user)
- read_file / write_file / list_dir: filesystem operations
- web_search: search the web and retrieve information
- create_todo / get_todo / mark_todo_done: plan multi-step tasks and track progress
- backup_codebase: create full backup before self-modification
- run_tests: run pytest in subprocess (default: tests/test_cli.py)
- run_agent_subprocess: run agent with a task in a fresh subprocess (loads code from disk)
- git_status / git_add / git_commit / git_push: version control (git_push uses GH_TOKEN)
- run_gh: run gh CLI (pr list, repo view, etc.). Uses GH_TOKEN from GHTOKEN.txt or env.
- request_restart: request process restart to load new code (TG bot only)

Rules:
1. Always use tools when the task requires interacting with the OS, files, or the web.
2. For shell commands, prefer simple one-liners. Avoid interactive commands.
3. When writing code/scripts, write them to files using write_file, then execute with run_shell.
4. For research tasks, use web_search to find information, then synthesize a clear answer.
5. Be concise and precise in your final answers.
6. If a task asks you to write a script, always save it to a file AND execute it to verify it works.

Multi-step tasks (TODO):
7. For complex tasks, use create_todo with steps, then execute each and mark_todo_done.
8. Check get_todo to see progress. Do not skip steps.

Self-modification (adding capabilities, rewriting your own code):
9. ALWAYS call backup_codebase BEFORE making any changes to agent code.
10. Use create_todo to plan: backup, implement, run_tests, run_agent_subprocess to verify.
11. After changes pass tests: git_add(["."]), git_commit("descriptive message"), git_push().
12. In your final report, summarize what was done, test results, and commit hash.
13. When running as TG bot, call request_restart() at the end so the bot restarts with new code.
14. Never kill the current process before validation. Always test in subprocess first.
15. GitHub: GHTOKEN.txt or GH_TOKEN env. Use run_gh for gh CLI.
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
    from agent.tools.filesystem import list_dir, read_file, write_file
    from agent.tools.gh import run_gh
    from agent.tools.git import git_add, git_commit, git_push, git_status
    from agent.tools.restart import request_restart
    from agent.tools.self_test import backup_codebase, run_agent_subprocess, run_tests
    from agent.tools.shell import run_shell
    from agent.tools.todo import create_todo, get_todo, mark_todo_done
    from agent.tools.web import web_search

    model = build_model(model_name, api_key)
    tools = [
        run_shell,
        read_file,
        write_file,
        list_dir,
        web_search,
        create_todo,
        get_todo,
        mark_todo_done,
        backup_codebase,
        run_tests,
        run_agent_subprocess,
        git_status,
        git_add,
        git_commit,
        git_push,
        run_gh,
        request_restart,
    ]
    return Agent(model, system_prompt=SYSTEM_PROMPT, tools=tools)
