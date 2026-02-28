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

from agent.tools.shell import run_shell
from agent.tools.filesystem import read_file, write_file, list_dir
from agent.tools.web import web_search
from agent.tools.browser import (
    browser_navigate,
    browser_screenshot,
    browser_get_text,
    browser_click,
    browser_fill,
    browser_get_html,
    browser_get_url,
    browser_refresh,
)
from agent.tools.todo import create_todo, get_todo, mark_todo_done
from agent.tools.memory import recall, remember
from agent.tools.git import git_status, git_add, git_commit, git_push, git_pull, git_checkout
from agent.tools.gh import run_gh
from agent.tools.restart import request_restart
from agent.tools.agents_md import read_agents_md, get_agents_rules, get_agents_context
from agent.tools.skills import list_skills, get_skill, find_relevant_skills, create_skill
from agent.tools.subagents import (
    list_subagents,
    get_subagent,
    delegate_task,
    route_task,
    create_subagent,
)
from agent.tools.deep_research import deep_research, quick_research, compare_sources

# Self-test and backup tools are imported separately in the agent core

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
]
