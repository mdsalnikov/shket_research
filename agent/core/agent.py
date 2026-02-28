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
- deep_research: conduct multi-step autonomous research with synthesis
- quick_research: perform a quick single-step research query
- compare_sources: compare information across multiple sources
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
- read_agents_md: read AGENTS.md for project context and guidelines
- get_agents_rules: get rules from AGENTS.md
- get_agents_context: get context for a specific topic from AGENTS.md
- list_skills: list available skills
- get_skill: get a specific skill by name
- find_relevant_skills: find skills relevant to a task
- create_skill: create a new skill
- list_subagents: list available subagents
- get_subagent: get a specific subagent
- delegate_task: delegate a task to a subagent
- route_task: automatically route a task to appropriate subagent
- create_subagent: create a new subagent

Rules:
1. Always use tools when the task requires interacting with the OS, files, or the web.
2. For shell commands, prefer simple one-liners. Avoid interactive commands.
3. When writing code/scripts, write them to a file using write_file, then execute with run_shell.
4. For research tasks:
   - Use web_search for simple queries
   - Use deep_research for complex multi-step research
   - Use quick_research for fast lookups
   - Use compare_sources when verification is needed
5. Be concise and precise in your final answers.
6. If a task asks you to write a script, always save it to a file AND execute it to verify it works.

Multi-step tasks (TODO):
7. For complex tasks, use create_todo with steps, then execute each and mark_todo_done.
8. Check get_todo to see progress. Do not skip steps.

AGENTS.md Support:
- Always read AGENTS.md at the start of complex tasks
- Follow rules and guidelines from AGENTS.md
- Use get_agents_context for topic-specific guidance

Skills System:
- Use find_relevant_skills to discover domain expertise
- Skills provide patterns and best practices for specific tasks
- Create new skills for recurring task patterns

Subagents:
- Use route_task to automatically delegate to specialized subagents
- Use delegate_task for explicit delegation
- Subagents have isolated context and specialized capabilities

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
- Do NOT run_gh("pr merge"). Ask the user to review and merge the PR.
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
    if provider == "openrouter" and not (api_key or OPENROUTER_API_KEY):
        logger.warning("OpenRouter requested but OPENROUTER_API_KEY is not set; using vLLM")
        provider = "vllm"

    if provider == "openrouter":
        logger.info("Building OpenRouter model: %s", model_name or OPENROUTER_MODEL_NAME)
        return build_openrouter_model(model_name, api_key)
    else:
        logger.info("Building vLLM model: %s", model_name or VLLM_MODEL_NAME)
        return build_vllm_model(model_name, base_url=None, api_key=None)


def build_agent(
    model: OpenAIChatModel | OpenRouterModel | None = None,
    provider: str | None = None,
    system_prompt: str | None = None,
) -> Agent[AgentDeps]:
    """Build agent with model and tools.
    
    Args:
        model: Pre-configured model (optional)
        provider: 'vllm' or 'openrouter' (used if model not provided)
        system_prompt: Override system prompt (optional)
        
    Returns:
        Configured Pydantic AI Agent
        
    """
    if model is None:
        model = build_model(provider=provider)
    
    from agent.tools import (
        run_shell,
        read_file,
        write_file,
        list_dir,
        web_search,
        deep_research,
        quick_research,
        compare_sources,
        create_todo,
        get_todo,
        mark_todo_done,
        recall,
        remember,
        git_status,
        git_add,
        git_commit,
        git_push,
        git_pull,
        git_checkout,
        run_gh,
        request_restart,
        read_agents_md,
        get_agents_rules,
        get_agents_context,
        list_skills,
        get_skill,
        find_relevant_skills,
        create_skill,
        list_subagents,
        get_subagent,
        delegate_task,
        route_task,
        create_subagent,
    )
    from agent.core.agent import backup_codebase, list_backups, restore_from_backup
    from agent.tools.self_test import run_tests, run_agent_subprocess
    
    agent = Agent[AgentDeps](
        model=model,
        system_prompt=system_prompt or SYSTEM_PROMPT,
        deps_type=AgentDeps,
    )
    
    # Register tools
    agent.tool()(run_shell)
    agent.tool()(read_file)
    agent.tool()(write_file)
    agent.tool()(list_dir)
    agent.tool()(web_search)
    agent.tool()(deep_research)
    agent.tool()(quick_research)
    agent.tool()(compare_sources)
    agent.tool()(create_todo)
    agent.tool()(get_todo)
    agent.tool()(mark_todo_done)
    agent.tool()(recall)
    agent.tool()(remember)
    agent.tool()(git_status)
    agent.tool()(git_add)
    agent.tool()(git_commit)
    agent.tool()(git_push)
    agent.tool()(git_pull)
    agent.tool()(git_checkout)
    agent.tool()(run_gh)
    agent.tool()(request_restart)
    agent.tool()(read_agents_md)
    agent.tool()(get_agents_rules)
    agent.tool()(get_agents_context)
    agent.tool()(list_skills)
    agent.tool()(get_skill)
    agent.tool()(find_relevant_skills)
    agent.tool()(create_skill)
    agent.tool()(list_subagents)
    agent.tool()(get_subagent)
    agent.tool()(delegate_task)
    agent.tool()(route_task)
    agent.tool()(create_subagent)
    agent.tool()(backup_codebase)
    agent.tool()(list_backups)
    agent.tool()(restore_from_backup)
    agent.tool()(run_tests)
    agent.tool()(run_agent_subprocess)
    
    return agent


def build_session_agent(
    model: OpenAIChatModel | OpenRouterModel | None = None,
    provider: str | None = None,
    system_prompt: str | None = None,
) -> Agent[AgentDeps]:
    """Build agent with session support.
    
    This is the same as build_agent but explicitly for session-based
    interactions with SQLite persistence.
    
    Args:
        model: Pre-configured model (optional)
        provider: 'vllm' or 'openrouter' (used if model not provided)
        system_prompt: Override system prompt (optional)
        
    Returns:
        Configured Pydantic AI Agent with session support
        
    """
    return build_agent(model=model, provider=provider, system_prompt=system_prompt)
