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
- browser_navigate: navigate to a URL and extract page content
- browser_screenshot: take a screenshot of the current page
- browser_get_text: extract text from elements using CSS selector
- browser_click: click on an element using CSS selector
- browser_fill: fill a form field with text
- browser_get_html: get full page HTML
- browser_get_url: get current page URL
- browser_refresh: refresh the current page
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
4. For web tasks:
   - Use web_search for simple queries
   - Use browser_navigate to visit specific URLs
   - Use browser_get_text to extract content from pages
   - Use browser_screenshot to capture visual state
   - Use browser_click and browser_fill for interaction
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
- CODE-SIMPLIFIER: After self-modification, ALWAYS delegate to code-simplifier subagent

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

PHASE 4 — CODE SIMPLIFICATION (MANDATORY AFTER SELF-MODIFICATION):
- **delegate_task("code-simplifier", "Review and simplify the recently modified code")**
- The code-simplifier subagent will:
  * Analyze recently modified code for clarity and maintainability
  * Apply project standards from AGENTS.md
  * Simplify complex code while preserving functionality
  * Run tests to ensure nothing broke
  * Provide a summary of improvements made
- This step ensures code quality and consistency after self-modification

ROLLBACK (if anything fails after you edited files):
- Use restore_from_backup(backup_dir) with the backup dir you created (e.g. from list_backups()).
- Then fix the code and re-run tests; do not push until everything passes.

RULES:
- Do not remove or weaken backup, list_backups, restore_from_backup, or this protocol.
- Never skip backup_codebase(), run_tests(), run_agent_subprocess(), or code-simplifier
- Never push or open a PR before tests and run_agent_subprocess succeed
- Never merge a PR yourself unless the user explicitly asked you to
- Prefer small, atomic changes; one logical change per run
- ALWAYS run code-simplifier after successful self-modification

=============================================================================

IMPORTANT: Git operations (push/pull) use gh CLI for authentication.
No SSH keys required - gh CLI provides credentials via GH_TOKEN.
Always use run_gh for GitHub operations (pr create, pr merge, pr view, etc.).

Session Management (OpenClaw-inspired):
- Sessions are stored in SQLite with per-chat isolation
- Memory uses L0/L1/L2 hierarchy for efficient retrieval
- Use 'remember' to save important information across sessions
- Use 'recall' to retrieve information when needed

Self-Healing System:
- Automatic error classification and recovery
- Context compression when approaching token limits
- Fallback responses for unrecoverable errors
- Progress tracking from assistant messages

Error Types:
- CONTEXT_OVERFLOW: Compress context and retry
- NETWORK_ERROR: Exponential backoff and retry
- TIMEOUT: Exponential backoff and retry
- TOOL_ERROR: Retry with adjusted parameters
- UNRECOVERABLE: Provide helpful fallback message

Progress Tracking:
- Use create_todo for multi-step tasks
- Mark steps complete with mark_todo_done
- Progress visible to user in real-time
- Helps with long-running tasks and transparency
"""


def create_agent(deps: AgentDeps) -> Agent[AgentDeps]:
    """Create and configure the agent with tools and system prompt.
    
    Args:
        deps: Dependency injection container with all tools
        
    Returns:
        Configured Pydantic AI agent
    """
    # Determine model based on provider
    provider = deps.config.PROVIDER_DEFAULT or PROVIDER_DEFAULT
    
    if provider == "openrouter":
        model = OpenRouterModel(
            model_name=deps.config.OPENROUTER_MODEL_NAME or OPENROUTER_MODEL_NAME,
            provider=OpenRouterProvider(api_key=deps.config.OPENROUTER_API_KEY or OPENROUTER_API_KEY),
        )
    else:  # vllm (default)
        model = OpenAIChatModel(
            model_name=deps.config.VLLM_MODEL_NAME or VLLM_MODEL_NAME,
            provider=OpenAIProvider(
                base_url=deps.config.VLLM_BASE_URL or VLLM_BASE_URL,
                api_key=deps.config.VLLM_API_KEY or VLLM_API_KEY,
            ),
        )
    
    # Create agent with system prompt
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT.format(version=VERSION),
        deps_type=AgentDeps,
    )
    
    # Register all tools
    from agent.tools import (
        # Shell & filesystem
        run_shell,
        read_file,
        write_file,
        list_dir,
        # Web & browser
        web_search,
        browser_navigate,
        browser_screenshot,
        browser_get_text,
        browser_click,
        browser_fill,
        browser_get_html,
        browser_get_url,
        browser_refresh,
        # Deep research
        deep_research,
        quick_research,
        compare_sources,
        # TODO management
        create_todo,
        get_todo,
        mark_todo_done,
        # Backup & recovery
        backup_codebase,
        list_backups,
        restore_from_backup,
        # Testing
        run_tests,
        run_agent_subprocess,
        # Git
        git_status,
        git_add,
        git_commit,
        git_push,
        git_pull,
        git_checkout,
        # GitHub CLI
        run_gh,
        # Restart
        request_restart,
        # Memory
        recall,
        remember,
        # AGENTS.md
        read_agents_md,
        get_agents_rules,
        get_agents_context,
        # Skills
        list_skills,
        get_skill,
        find_relevant_skills,
        create_skill,
        # Subagents
        list_subagents,
        get_subagent,
        delegate_task,
        route_task,
        create_subagent,
    )
    
    # Register tools with the agent
    agent.tool(run_shell)
    agent.tool(read_file)
    agent.tool(write_file)
    agent.tool(list_dir)
    agent.tool(web_search)
    agent.tool(browser_navigate)
    agent.tool(browser_screenshot)
    agent.tool(browser_get_text)
    agent.tool(browser_click)
    agent.tool(browser_fill)
    agent.tool(browser_get_html)
    agent.tool(browser_get_url)
    agent.tool(browser_refresh)
    agent.tool(deep_research)
    agent.tool(quick_research)
    agent.tool(compare_sources)
    agent.tool(create_todo)
    agent.tool(get_todo)
    agent.tool(mark_todo_done)
    agent.tool(backup_codebase)
    agent.tool(list_backups)
    agent.tool(restore_from_backup)
    agent.tool(run_tests)
    agent.tool(run_agent_subprocess)
    agent.tool(git_status)
    agent.tool(git_add)
    agent.tool(git_commit)
    agent.tool(git_push)
    agent.tool(git_pull)
    agent.tool(git_checkout)
    agent.tool(run_gh)
    agent.tool(request_restart)
    agent.tool(recall)
    agent.tool(remember)
    agent.tool(read_agents_md)
    agent.tool(get_agents_rules)
    agent.tool(get_agents_context)
    agent.tool(list_skills)
    agent.tool(get_skill)
    agent.tool(find_relevant_skills)
    agent.tool(create_skill)
    agent.tool(list_subagents)
    agent.tool(get_subagent)
    agent.tool(delegate_task)
    agent.tool(route_task)
    agent.tool(create_subagent)
    
    logger.info(f"Agent created with {provider} provider, model: {model.model_name}")
    
    return agent
