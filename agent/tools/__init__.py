"""Agent tools package.

This package contains all tool implementations for the Shket Research Agent.
Tools are categorized into:
- Core tools: shell, filesystem, web search, browser
- Development tools: git, gh CLI, testing
- Agent tools: todo, backup, memory, self-test
- Context tools: agents_md (AGENTS.md parser), skills (skills system)
- Subagent tools: subagents (hierarchical agent architecture)
- Research tools: deep_research (advanced multi-step research)
"""

from pydantic_ai import Agent

from agent.tools.agents_md import get_agents_context, get_agents_rules, read_agents_md
from agent.tools.browser import (
    browser_click,
    browser_fill,
    browser_get_html,
    browser_get_text,
    browser_get_url,
    browser_navigate,
    browser_refresh,
    browser_screenshot,
)
from agent.tools.deep_research import compare_sources, deep_research, quick_research
from agent.tools.filesystem import list_dir, read_file, write_file
from agent.tools.gh import run_gh
from agent.tools.git import git_add, git_checkout, git_commit, git_pull, git_push, git_status
from agent.tools.memory import recall, remember
from agent.tools.restart import request_restart
from agent.tools.self_test import (
    backup_codebase,
    get_recent_bot_errors,
    list_backups,
    restore_from_backup,
    run_agent_subprocess,
    run_tests,
)
from agent.tools.shell import run_shell
from agent.tools.skills import create_skill, find_relevant_skills, get_skill, list_skills
from agent.tools.subagents import (
    create_subagent,
    delegate_task,
    get_subagent,
    list_subagents,
    route_task,
)
from agent.tools.todo import create_todo, get_todo, mark_todo_done
from agent.tools.web import web_search

__all__ = [
    # Core tools
    "run_shell",
    "read_file",
    "write_file",
    "list_dir",
    "web_search",
    # Browser tools
    "browser_navigate",
    "browser_screenshot",
    "browser_get_text",
    "browser_click",
    "browser_fill",
    "browser_get_html",
    "browser_get_url",
    "browser_refresh",
    # Todo tools
    "create_todo",
    "get_todo",
    "mark_todo_done",
    # Memory tools
    "recall",
    "remember",
    # Git tools
    "git_status",
    "git_add",
    "git_commit",
    "git_push",
    "git_pull",
    "git_checkout",
    # GitHub CLI
    "run_gh",
    # Agent tools
    "request_restart",
    # AGENTS.md tools
    "read_agents_md",
    "get_agents_rules",
    "get_agents_context",
    # Skills tools
    "list_skills",
    "get_skill",
    "find_relevant_skills",
    "create_skill",
    # Subagent tools
    "list_subagents",
    "get_subagent",
    "delegate_task",
    "route_task",
    "create_subagent",
    # Deep research tools
    "deep_research",
    "quick_research",
    "compare_sources",
    # Self-test and backup tools
    "backup_codebase",
    "get_recent_bot_errors",
    "list_backups",
    "restore_from_backup",
    "run_tests",
    "run_agent_subprocess",
]


def register_tools(agent: Agent) -> None:
    """Register all tools with the agent.

    Args:
        agent: Pydantic AI agent instance to register tools with.
    """
    # Core tools (no context needed)
    agent.tool_plain(run_shell)
    agent.tool_plain(read_file)
    agent.tool_plain(write_file)
    agent.tool_plain(list_dir)
    agent.tool_plain(web_search)

    # Browser tools (no context needed)
    agent.tool_plain(browser_navigate)
    agent.tool_plain(browser_screenshot)
    agent.tool_plain(browser_get_text)
    agent.tool_plain(browser_click)
    agent.tool_plain(browser_fill)
    agent.tool_plain(browser_get_html)
    agent.tool_plain(browser_get_url)
    agent.tool_plain(browser_refresh)

    # Todo tools (no context needed)
    agent.tool_plain(create_todo)
    agent.tool_plain(get_todo)
    agent.tool_plain(mark_todo_done)

    # Memory tools (need RunContext)
    agent.tool(recall)
    agent.tool(remember)

    # Git tools (no context needed)
    agent.tool_plain(git_status)
    agent.tool_plain(git_add)
    agent.tool_plain(git_commit)
    agent.tool_plain(git_push)
    agent.tool_plain(git_pull)
    agent.tool_plain(git_checkout)

    # GitHub CLI (no context needed)
    agent.tool_plain(run_gh)

    # Agent tools (no context needed)
    agent.tool_plain(request_restart)

    # AGENTS.md tools (no context needed)
    agent.tool_plain(read_agents_md)
    agent.tool_plain(get_agents_rules)
    agent.tool_plain(get_agents_context)

    # Skills tools (no context needed)
    agent.tool_plain(list_skills)
    agent.tool_plain(get_skill)
    agent.tool_plain(find_relevant_skills)
    agent.tool_plain(create_skill)

    # Subagent tools (no context needed)
    agent.tool_plain(list_subagents)
    agent.tool_plain(get_subagent)
    agent.tool_plain(delegate_task)
    agent.tool_plain(route_task)
    agent.tool_plain(create_subagent)

    # Deep research tools (no context needed)
    agent.tool_plain(deep_research)
    agent.tool_plain(quick_research)
    agent.tool_plain(compare_sources)

    # Self-test and backup tools (no context needed)
    agent.tool_plain(backup_codebase)
    agent.tool_plain(get_recent_bot_errors)
    agent.tool_plain(list_backups)
    agent.tool_plain(restore_from_backup)
    agent.tool_plain(run_tests)
    agent.tool_plain(run_agent_subprocess)
