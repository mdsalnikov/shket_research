# 🤖 Shket Research Agent

Autonomous LLM-powered agent for executing tasks on an Ubuntu server — controllable via CLI and Telegram bot.

**Version:** 0.4.6 | **Provider:** vLLM (default) / OpenRouter | **Session:** SQLite

---

## Overview

Shket Research Agent is a self-sufficient AI agent built around a central orchestration core. It accepts commands through a CLI or a Telegram bot, executes arbitrary tasks on the host OS, and logs every action it takes. The agent is designed for research workflows, including web browsing, code execution, environment management, deep research tasks, and self-modification with automatic code simplification.

---

## Architecture

```
┌──────────────────────────────────────────┐
│              Control Interfaces          │
│         CLI            Telegram Bot      │
└──────────────┬─────────────┬────────────┘
               │             │
               ▼             ▼
        ┌──────────────────────┐
        │      Agent Core      │  ← all LLM calls go through here
        │  (pydantic-ai / etc) │
        └──────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
   LLM Backend       Tool Executor
 (VLLM / OpenRouter)  (shell, browser, fs...)
               │
               ▼
         Logger (file + Telegram)
```

---

## Tools

The agent has access to the following tools. All tool calls are routed through the Agent Core and logged automatically.

### 🐚 Shell
Execute arbitrary OS commands on the host Ubuntu server (non-root user).

### 🌐 Browser
Headless web browsing for environments without a GUI.

- Navigate to URLs
- Extract content with CSS selectors
- Take screenshots
- Click and fill forms
- Get full page HTML

### 📁 Filesystem
Read, write, list, and manage files on the host OS.

### 🔍 Deep Research
Multi-step research workflows combining web search and synthesis.

- `deep_research`: Complex multi-step research with synthesis
- `quick_research`: Fast single-step lookups
- `compare_sources`: Verify information across sources

### 📋 Task Planning (TODO)
Plan and track multi-step tasks.

- `create_todo`: Create task list with steps
- `get_todo`: Check current progress
- `mark_todo_done`: Mark step as complete

### 💾 Backup & Recovery
Self-modification safety tools.

- `backup_codebase`: Create full backup (keeps last 5)
- `list_backups`: List available backups
- `restore_from_backup`: Restore from backup after failed edit

### 🧪 Testing & Self-Repair
Validate code changes and fix errors from logs.

- `run_tests`: Run pytest in subprocess
- `run_agent_subprocess`: Test agent in fresh subprocess
- `get_recent_bot_errors`: Read last N lines of bot error log (for self-repair)

### 🔧 Version Control
Git operations with GitHub CLI integration.

- `git_status`, `git_add`, `git_commit`
- `git_push`, `git_pull`, `git_checkout`
- `run_gh`: GitHub CLI (pr create, pr merge, etc.)

### 🧠 Memory System
Long-term memory with L0/L1/L2 hierarchy.

- `recall`: Search memory by query
- `remember`: Save information to memory
- Categories: System, Environment, Skill, Project, Comm, Security

### 📖 AGENTS.md Support
Access project documentation dynamically.

- `read_agents_md`: Read full AGENTS.md
- `get_agents_rules`: Extract rules
- `get_agents_context`: Get topic-specific guidance

### 🎯 Skills System
Domain expertise and best practices.

- `list_skills`: List available skills
- `get_skill`: Get specific skill
- `find_relevant_skills`: Find skills for task
- `create_skill`: Create new skill

### 🤖 Subagents
Specialized agents for specific tasks.

- `list_subagents`: List available subagents
- `get_subagent`: Get subagent details
- `delegate_task`: Explicit delegation
- `route_task`: Auto-routing to appropriate subagent
- `create_subagent`: Create new subagent

**Built-in subagents:**
- `coder`: Code generation and modification
- `researcher`: Information gathering
- `reviewer`: Code review and QA
- `tester`: Test creation and execution
- `code-simplifier`: Post-modification code simplification (MANDATORY)
- `self-repair`: Fix errors from bot/activity logs (tracebacks, crashes)

### 🔄 Self-Modification
- `request_restart`: Request process restart (TG bot only)

---

## Control Interfaces

### CLI

```bash
python -m agent <command> [args]
```

| Command | Description |
|---|---|
| `run "task"` | Execute a task in natural language |
| `status` | Show agent status and version |
| `memory` | Show memory summary (L0) |
| `clear` | Clear session context |
| `context` | Show session stats (messages, tokens) |
| `resume` | Resume incomplete resumable task |
| `long list [--chat-id N] [--limit N]` | List resumable tasks |
| `long show <task_id>` | Show task details |
| `logs [N]` | Show last N log entries (default 30) |
| `self-repair-check [--dry-run]` | Check logs, run self-repair, merge PR, restart (for cron) |

**Examples:**

```bash
# Run a task
python -m agent run "find all Python files larger than 1MB"

# Check status
python -m agent status

# Show memory
python -m agent memory

# View session context
python -m agent context

# List long-running tasks
python -m agent long list --limit 10

# Show last 50 log entries
python -m agent logs 50

# Use OpenRouter provider
python -m agent run "research topic" --provider openrouter
```

### Telegram Bot

Start the bot with `python -m agent bot`, then interact via Telegram.

**Commands:**

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Full command reference |
| `/status` | Agent status, uptime, resumable tasks |
| `/tasks` | Currently running tasks by chat |
| `/long <goal>` | Long-running task (survives restart) |
| `/longlist` | List long tasks (running/completed/failed) |
| `/provider` | Switch LLM provider (vllm/openrouter) |
| `/context` | Session stats (messages, tokens, age) |
| `/clear` | Clear session context |
| `/logs [N]` | Last N log entries (default 30) |
| `/errors [N]` | Last N bot error log lines (for self-repair) |
| `/exportlogs` | Download full log file |
| `/panic` | 🛑 Emergency halt — kill all processes |

Any text message (not a command) is treated as a task for the agent. Tasks run asynchronously — the bot stays responsive while tasks execute, and you can send multiple tasks in parallel.

**Progress Tracking:**
- Real-time updates on each task step
- TODO progress notifications
- Step completion tracking

---

## Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for [OpenRouter](https://openrouter.ai) |
| `TG_BOT_KEY` | Telegram Bot API token (from [@BotFather](https://t.me/BotFather)) |
| `GH_TOKEN` | GitHub token for `git push` and `gh` CLI |
| `AGENT_MAX_RETRIES` | Retries on task failure (default 3) |
| `RESTART_CMD` | Command run after cron self-repair merge (e.g. `systemctl restart shket-bot`) |
| `VLLM_BASE_URL` | Local vLLM endpoint URL |
| `VLLM_MODEL_NAME` | Model name for vLLM |

**Setup:**
```bash
cp .env.example .env
# Fill in OPENROUTER_API_KEY and TG_BOT_KEY
```

**GitHub Token:**
Put your GitHub token in `GHTOKEN.txt` (project root) or set `GH_TOKEN` in `.env`:
```
# GHTOKEN.txt
github_pat_xxxx...
```

---

## Supported LLM Backends

### OpenRouter (development)
| Model | OpenRouter ID |
|---|---|
| Qwen 3.5 122B A10B | `qwen/qwen3.5-122b-a10b` |
| GPT OSS 120B | `openai/gpt-oss-120b` |
| Gemini 3 Flash Preview | `google/gemini-3-flash-preview` |

### VLLM (local inference, default)
Configured via `VLLM_BASE_URL` and `VLLM_MODEL_NAME` in config.

---

## Self-Modification Protocol

When the agent modifies its own code, it follows this protocol:

**PHASE 1 — PREPARE:**
1. `backup_codebase()` — create full backup
2. Read current files to understand changes
3. Create branch for non-trivial changes

**PHASE 2 — EDIT & VERIFY:**
4. Make changes with `write_file`
5. Update VERSION (PATCH/MINOR/MAJOR)
6. Run `run_tests()` — verify nothing broke
7. Run `run_agent_subprocess("run status")` — test new code

**PHASE 3 — COMMIT:**
- Small fix: commit to main, push
- Large change: create PR, user reviews and merges

**PHASE 4 — CODE SIMPLIFICATION (MANDATORY):**
8. `delegate_task("code-simplifier", "Review and simplify the recently modified code")`
   - Analyze code for complexity
   - Apply simplification patterns
   - Run tests to verify
   - Provide summary report

**ROLLBACK (if anything fails):**
- Use `restore_from_backup(backup_dir)` from `list_backups()`
- Fix code and re-run tests

**Scheduled self-repair (cron):**  
If errors appear in `logs/bot_errors.log`, run hourly: `python -m agent self-repair-check`. The agent fixes the code, runs tests, creates a branch and PR; the script then merges the PR, pulls main, and runs `RESTART_CMD` if set. See AGENTS.md for cron and `RESTART_CMD`.

---

## Session Support

SQLite-based session persistence (`data/sessions.db`):

- **Message history**: Full conversation context
- **Resumable tasks**: Long-running tasks survive restarts
- **Memory**: L0/L1/L2 hierarchy for long-term knowledge
- **Progress tracking**: Real-time step updates

---

## Getting Started

```bash
# 1. Clone the repo
git clone <repo-url>
cd <repo>

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Fill in OPENROUTER_API_KEY and TG_BOT_KEY

# 5. Run a task via CLI
python -m agent run "hello world"

# 6. Or start the Telegram bot
python -m agent bot
```

---

## Project Structure

```
agent/
├── core/              # LLM orchestration, agent builder, runner
│   ├── agent.py       # Agent configuration and builder
│   └── runner.py      # Task execution with retries
├── tools/             # Individual tools
│   ├── __init__.py    # Tool registration
│   ├── filesystem.py  # File operations
│   ├── web.py         # Web search and browser
│   ├── deep_research.py  # Multi-step research
│   ├── todo.py        # Task planning
│   ├── self_test.py   # Backup, tests, subprocess
│   ├── git.py         # Git operations
│   ├── gh.py          # GitHub CLI
│   ├── memory.py      # Memory system
│   ├── agents_md.py   # AGENTS.md support
│   ├── skills.py      # Skills system
│   └── subagents.py   # Subagent system
├── interfaces/        # Control interfaces
│   ├── cli.py         # CLI entrypoint
│   └── telegram.py    # Telegram bot
├── config.py          # Configuration
├── dependencies.py    # Dependency injection
├── session_globals.py # SQLite session management
├── healing.py         # Self-healing error recovery
├── progress.py        # Progress tracking
├── activity_log.py    # Activity logging
└── self_repair_cron.py # Scheduled self-repair (cron)

subagents/             # Subagent definitions
├── coder.yaml
├── researcher.yaml
├── reviewer.yaml
├── tester.yaml
├── code-simplifier.yaml
└── self-repair.yaml   # Fix errors from logs

skills/                # Skill definitions
└── *.md

agents/                # Agent documentation
└── code-simplifier.md

data/                  # Runtime data
└── sessions.db        # SQLite session database

logs/                  # Log files
├── agent.log
└── bot_errors.log     # Bot tracebacks (for self-repair)
```

**Development (lint/format):**  
With dev deps (`pip install -e ".[dev]"`): `ruff check .` and `ruff format .`; tests: `pytest tests/ -v`.

**CI (GitHub Actions):** On every push and PR to `main`, workflow **CI** runs ruff (check + format) and pytest (excluding LLM tests and `test_resumable_tasks`). Set branch protection so the PR cannot be merged until CI passes. If CI fails, run the agent to fix the branch (fix code, push, re-run CI); merge only when green, then restart the bot.

---

## Safety & Self-Preservation

- **Backup before changes**: Always create backup before self-modification
- **Branch for changes**: Non-trivial changes on separate branch
- **Test before push**: Run tests and subprocess validation
- **Rollback support**: `restore_from_backup` for failed edits
- **Emergency stop**: `/panic` command kills all processes
- **Code simplification**: Mandatory review after self-modification

---

## Recommended Stack

| Component | Technology |
|---|---|
| Agent framework | [pydantic-ai](https://ai.pydantic.dev) |
| LLM routing | OpenRouter (dev) / VLLM (prod) |
| Telegram interface | [python-telegram-bot](https://python-telegram-bot.org) |
| Browser | [agent-browser (Vercel Labs)](https://github.com/vercel-labs/agent-browser) |
| Session mgmt | SQLite |
| Package mgmt | Conda |
| Logging | Python `logging` → file + Telegram |

---

## License

MIT
