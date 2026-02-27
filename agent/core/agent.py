"""Agent configuration and builder with session support.

This module provides the agent builder with Pydantic AI integration,
SQLite session persistence, and dependency injection.

Supports two providers:
- vLLM (default): Local OpenAI-compatible API
- OpenRouter: Cloud API with many models
"""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from agent.config import (
    DEFAULT_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL_NAME,
    VLLM_BASE_URL,
    VLLM_MODEL_NAME,
    VLLM_API_KEY,
    PROVIDER_DEFAULT,
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
- list_backups: list .backup_* dirs (for rollback)
- restore_from_backup(backup_dir): restore codebase from a backup after failed self-edit
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

When the user asks you to modify, fix, add, or improve YOUR OWN CODE follow
this protocol. Keep steps small and explicit (suited for large models like GPT-OSS-120B).

PHASE 1 — PREPARE (never skip):
1. **backup_codebase()** — create full backup before any changes
2. **Read current files** — use read_file to understand the code you will change
3. **Branch (for non-trivial changes):** if you are on main and the change is more
   than a one-file fix, create a branch: run_shell("git checkout -b agent-edit-<short-name>")
   Example: agent-edit-fix-telegram-log

PHASE 2 — EDIT & VERIFY:
4. **Make changes** — use write_file only for the files you need to change
5. **Update VERSION** — bump PATCH (bugfix), MINOR (feature), or MAJOR (breaking); update VERSION file
6. **run_tests()** — use run_tests("tests/test_cli.py") and for agent code also run_tests("tests/test_session.py")
   (or run_tests("tests/") for full suite). Do not push until tests pass.
7. **run_agent_subprocess("run status")** — mandatory: run the agent in a fresh subprocess with
   a concrete task so the NEW code is loaded and exercised. Use exactly "run status" or similar
   non-trivial task, not "echo hello".

PHASE 3A — SMALL FIX (single file, typo, config): commit to main
- If all tests and run_agent_subprocess passed: git_add(["."]), git_commit("message with version"),
  git_push() (you are on main). If TG bot: request_restart().

PHASE 3B — LARGER CHANGE (multiple files, new feature): use PR, do not merge yourself
- If all tests and run_agent_subprocess passed: git_add(["."]), git_commit("message with version"),
  git_push() (you are on your branch), then run_gh("pr create --title '...' --body '...'").
- Verify: run_gh("pr view") and run_tests("tests/test_cli.py") again.
- Do NOT run run_gh("pr merge"). Ask the user to review and merge the PR.
- After the user has merged: git_checkout("main"), git_pull("main"). If TG bot: request_restart().

ROLLBACK (if anything fails after you edited files):
- Use restore_from_backup(backup_dir) with the backup dir you created (e.g. from list_backups()).
- Then fix the code and re-run tests; do not push until everything passes.

RULES:
- Do not remove or weaken backup, list_backups, restore_from_backup, or this protocol.
- Never skip backup_codebase(), run_tests(), or run_agent_subprocess()
- Never push or open a PR before tests and run_agent_subprocess succeed
- Never merge a PR yourself unless the user explicitly asked you to
- Prefer small, atomic changes; one logical change per run

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


def build_vllm_model(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> OpenAIChatModel:
    """Build vLLM model instance (OpenAI-compatible local API).
    
    Args:
        model_name: Model identifier (e.g., 'openai/gpt-oss-120b')
        base_url: vLLM API base URL (default: http://localhost:8000/v1)
        api_key: API key (usually not needed for vLLM)
        
    Returns:
        Configured OpenAIChatModel instance for vLLM
        
    """
    provider = OpenAIProvider(
        base_url=base_url or VLLM_BASE_URL,
        api_key=api_key or VLLM_API_KEY,
    )
    return OpenAIChatModel(
        model_name=model_name or VLLM_MODEL_NAME,
        provider=provider,
    )


def build_openrouter_model(
    model_name: str | None = None,
    api_key: str | None = None,
) -> OpenRouterModel:
    """Build OpenRouter model instance.
    
    Args:
        model_name: Model identifier (e.g., 'anthropic/claude-3.5-sonnet')
        api_key: OpenRouter API key
        
    Returns:
        Configured OpenRouterModel instance
        
    """
    return OpenRouterModel(
        model_name=model_name or OPENROUTER_MODEL_NAME,
        provider=OpenRouterProvider(api_key=api_key or OPENROUTER_API_KEY),
    )


def build_model(
    model_name: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
) -> OpenAIChatModel | OpenRouterModel:
    """Build model instance based on provider.
    
    Args:
        model_name: Model identifier
        api_key: API key (provider-specific)
        provider: 'vllm' or 'openrouter' (default: from config)
        
    Returns:
        Configured model instance
        
    """
    provider = provider or PROVIDER_DEFAULT
    
    if provider == "openrouter":
        logger.info(f"Using OpenRouter provider with model: {model_name or OPENROUTER_MODEL_NAME}")
        return build_openrouter_model(model_name, api_key)
    else:
        logger.info(f"Using vLLM provider at {VLLM_BASE_URL} with model: {model_name or VLLM_MODEL_NAME}")
        return build_vllm_model(model_name, api_key=api_key)


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
    from agent.tools.self_test import (
        backup_codebase,
        list_backups,
        restore_from_backup,
        run_agent_subprocess,
        run_tests,
    )
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
        list_backups,
        restore_from_backup,
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
    provider: str | None = None,
) -> Agent:
    """Build agent with all tools (legacy mode without dependencies).
    
    This creates a simple agent without session support.
    Use build_session_agent for full SQLite session persistence.
    
    Args:
        model_name: Model identifier
        api_key: API key
        provider: 'vllm' or 'openrouter'
        
    Returns:
        Agent instance (without session support)
        
    """
    model = build_model(model_name, api_key, provider)
    tools = get_all_tools()

    return Agent(model, system_prompt=SYSTEM_PROMPT, tools=tools)


def build_session_agent(
    model_name: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
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
        api_key: API key
        provider: 'vllm' or 'openrouter'
        
    Returns:
        Agent instance with session support
        
    """
    model = build_model(model_name, api_key, provider)
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
        deps = ctx.deps
        
        # Build memory context if available
        memory_context = ""
        if deps.memory_l0:
            memory_context = "\n\n## Memory Context (L0)\n\n"
            for category, summaries in deps.memory_l0.items():
                if summaries:
                    memory_context += f"### {category}\n"
                    for summary in summaries:
                        memory_context += f"- {summary}\n"
                    memory_context += "\n"
        
        return SYSTEM_PROMPT + memory_context

    return agent
