"""Agent configuration and builder with session support.

This module provides the agent builder with Pydantic AI integration,
SQLite session persistence, and dependency injection.
"""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from agent.config import (
    DEFAULT_MODEL,
    OPENROUTER_API_KEY,
    USE_VLLM,
    VLLM_BASE_URL,
    VERSION,
)
from agent.dependencies import AgentDeps

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Shket Research Agent v{version} — an autonomous AI assistant running on an Ubuntu server.

Tools:
- run_shell: execute shell commands on the host OS (non-root user)
- read_file / write_file / list_dir: filesystem operations
- web_search: search the web and retrieve information
- create_todo / get_todo / mark_todo_done: plan multi-step tasks and track progress
- backup_codebase: create full backup before self-modification
- run_tests: run pytest in subprocess (default: tests/test_cli.py)
- run_agent_subprocess: run agent with a task in a fresh subprocess (loads code from disk)
- git_status / git_add / git_commit / git_push / git_pull / git_checkout: version control
- run_gh: run gh CLI (pr create, pr merge, pr view, etc.). Uses GH_TOKEN from GHTOKEN.txt or env.
- request_restart: request process restart to load new code (TG bot only)
- recall: recall information from memory
- remember: save important information to memory

Rules:
1. Always use tools when the task requires interacting with the OS, files, or the web.
2. For shell commands, prefer simple one-liners. Avoid interactive commands.
3. When writing code/scripts, write them to a file using write_file, then execute with run_shell.
4. For research tasks, use web_search to find information, then synthesize a clear answer.
5. Be concise and precise in your final answers.
6. If a task asks you to write a script, always save it to a file AND execute it to verify it works.

Multi-step tasks (TODO):
7. For complex tasks, use create_todo with steps, then execute each and mark_todo_done.
8. Check get_todo to see progress. Do not skip steps.

=============================================================================
SELF-MODIFICATION PROTOCOL (when asked to change YOURSELF)
=============================================================================

When the user asks you to modify, fix, add, or improve YOUR OWN CODE:

MANDATORY STEPS (in order, never skip):
1. **backup_codebase()** — create full backup before any changes
2. **Read current files** — use read_file to understand current code
3. **Make changes** — use write_file to modify files
4. **run_tests()** — run pytest to verify changes work
5. **run_agent_subprocess(task)** — test that new code works in fresh process
6. If all tests pass:
   a. git_add(["."])
   b. git_commit("descriptive message about what changed")
   c. git_push()
7. Create PR: run_gh("pr create --title '...' --body '...'")
8. Verify PR: run_gh("pr view") and run_tests() again
9. Merge PR: run_gh("pr merge --merge")
10. git_checkout("main") → git_pull("main")
11. If running as TG bot: request_restart()

VERSION MANAGEMENT:
- Version is stored in VERSION file at project root
- When making changes to agent code, increment version:
  - MAJOR: breaking changes / major features
  - MINOR: new features / improvements
  - PATCH: bug fixes / small changes
- Update VERSION file with new version number
- Include version in git commit message

NEVER SKIP STEPS:
- Never skip backup_codebase()
- Never skip run_tests()
- Never skip run_agent_subprocess() for verification
- Never push without running tests first
- Never merge PR without verification

ERROR HANDLING:
- If tests fail, analyze errors and fix code
- Re-run tests after fixes
- If run_agent_subprocess fails, debug and fix
- Always ensure all tests pass before git operations

=============================================================================

IMPORTANT: Git operations (push/pull) use gh CLI for authentication.
No SSH keys required - gh CLI provides credentials via GH_TOKEN.
Always use run_gh for GitHub operations (pr create, pr merge, pr view, etc.).

Session Management (OpenClaw-inspired):
- Sessions are stored in SQLite with per-chat isolation
- Memory uses L0/L1/L2 hierarchy for efficient retrieval
- Use 'remember' to save important information across sessions
- Use 'recall' to retrieve stored memories
""".format(version=VERSION)


def build_model(
    model_name: str | None = None,
    api_key: str | None = None,
) -> OpenAIModel | OpenRouterModel:
    """Build model instance (VLLM local or OpenRouter cloud).

    Priority:
    1. VLLM local (USE_VLLM=true) - uses OpenAIModel with VLLM_BASE_URL
    2. OpenRouter cloud (fallback) - uses OpenRouterModel

    Args:
        model_name: Model identifier (e.g., 'openai/gpt-oss-120b')
        api_key: API key (for OpenRouter only)

    Returns:
        Configured model instance (OpenAIModel for VLLM, OpenRouterModel for cloud)

    """
    model_id = model_name or DEFAULT_MODEL

    # Use VLLM local endpoint if configured
    if USE_VLLM and VLLM_BASE_URL:
        logger.info(f"Using VLLM local endpoint: {VLLM_BASE_URL}")
        logger.info(f"Model: {model_id}")
        return OpenAIModel(
            model_id,
            provider=OpenAIProvider(base_url=VLLM_BASE_URL),
        )

    # Fallback to OpenRouter cloud
    logger.info(f"Using OpenRouter cloud endpoint")
    logger.info(f"Model: {model_id}")
    return OpenRouterModel(
        model_id,
        provider=OpenRouterProvider(api_key=api_key or OPENROUTER_API_KEY),
    )


def get_all_tools() -> list:
    """Get all available tools for the agent.

    Returns:
        List of tool functions

    """
    from agent.tools.filesystem import list_dir, read_file, write_file
    from agent.tools.gh import run_gh
    from agent.tools.git import (
        git_add,
        git_checkout,
        git_commit,
        git_pull,
        git_push,
        git_status,
    )
    from agent.tools.restart import request_restart
    from agent.tools.self_test import backup_codebase, run_agent_subprocess, run_tests
    from agent.tools.shell import run_shell
    from agent.tools.todo import create_todo, get_todo, mark_todo_done
    from agent.tools.web import web_search
    from agent.tools.memory import recall, remember

    return [
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
        git_pull,
        git_checkout,
        run_gh,
        request_restart,
        recall,
        remember,
    ]


def build_agent(
    model_name: str | None = None,
    api_key: str | None = None,
) -> Agent:
    """Build agent with all tools (legacy mode without dependencies).

    This creates a simple agent without session support.
    Use build_session_agent for full SQLite session persistence.

    Args:
        model_name: Model identifier
        api_key: API key (for OpenRouter only)

    Returns:
        Agent instance (without session support)

    """
    model = build_model(model_name, api_key)
    tools = get_all_tools()

    return Agent(model, system_prompt=SYSTEM_PROMPT, tools=tools)


def build_session_agent(
    model_name: str | None = None,
    api_key: str | None = None,
) -> Agent:
    """Build agent with session support (uses AgentDeps).

    This is the preferred way to build agents with SQLite persistence.
    The agent will have access to session history and memory through
    the RunContext passed to tools.

    Architecture (OpenClaw-inspired):
    - Sessions stored in SQLite with per-chat isolation
    - Memory with L0/L1/L2 hierarchy
    - Dependency injection via AgentDeps
    - Dynamic system prompt with memory context

    Args:
        model_name: Model identifier
        api_key: API key (for OpenRouter only)

    Returns:
        Agent instance with session support

    """
    model = build_model(model_name, api_key)
    tools = get_all_tools()

    agent = Agent(
        model,
        deps_type=AgentDeps,
        tools=tools,
    )

    # Add dynamic system prompt with memory context
    @agent.system_prompt
    async def get_system_prompt(ctx) -> str:
        """Get system prompt with optional memory context.

        Injects L0 memory summary into the system prompt for context
        continuity across sessions.

        """
        base_prompt = SYSTEM_PROMPT

        # Add memory context if available (L0 summary)
        if hasattr(ctx.deps, "memory") and ctx.deps.memory:
            memory_context = "\n\n## Memory Context (L0)\n"
            for category, entries in ctx.deps.memory.items():
                if entries:
                    memory_context += f"\n### {category}\n"
                    for entry in entries:
                        memory_context += f"- {entry['abstract']}\n"

            if memory_context != "\n\n## Memory Context (L0)\n":
                base_prompt += memory_context

        return base_prompt

    logger.debug("Session agent built with SQLite persistence")
    return agent
