"""Agent configuration and builder with session support.

This module provides the agent builder with Pydantic AI integration,
SQLite session persistence, and dependency injection.
"""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from agent.config import DEFAULT_MODEL, OPENROUTER_API_KEY
from agent.dependencies import AgentDeps

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

Self-modification (default cycle):
9. backup_codebase → make changes → run_tests → run_agent_subprocess to verify.
10. If OK: git_add(["."]), git_commit("msg"), git_push().
11. run_gh("pr create --title '...' --body '...'") — create PR to main.
12. Verify PR: run_gh("pr view") or run_tests again. If OK: run_gh("pr merge --merge").
13. git_checkout("main"), git_pull("main") — update local.
14. When TG bot: request_restart() — restart from new main.
15. Never skip validation. GitHub: GHTOKEN.txt or GH_TOKEN env.

IMPORTANT: Git operations (push/pull) use gh CLI for authentication.
No SSH keys required - gh CLI provides credentials via GH_TOKEN.
Always use run_gh for GitHub operations (pr create, pr merge, pr view, etc.).

Session Management (OpenClaw-inspired):
- Sessions are stored in SQLite with per-chat isolation
- Memory uses L0/L1/L2 hierarchy for efficient retrieval
- Use 'remember' to save important information across sessions
- Use 'recall' to retrieve stored memories
"""


def build_model(
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
        model_name or DEFAULT_MODEL,
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
        api_key: OpenRouter API key
        
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
        api_key: OpenRouter API key
        
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
        # Try to get memory context if deps available
        try:
            memory_context = await ctx.deps.get_context_summary()
            if memory_context:
                logger.debug("Injected memory context into system prompt")
                return f"{SYSTEM_PROMPT}\n\n{memory_context}"
        except Exception as e:
            logger.debug(f"Could not get memory context: {e}")
        return SYSTEM_PROMPT

    return agent
