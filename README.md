# 🤖 Shket Research Agent

Autonomous LLM-powered agent for executing tasks on an Ubuntu server — controllable via CLI and Telegram bot.

---

## Overview

Shket Research Agent is a self-sufficient AI agent built around a central orchestration core. It accepts commands through a CLI or a Telegram bot, executes arbitrary tasks on the host OS, and logs every action it takes. The agent is designed for research workflows, including web browsing, code execution, environment management, and deep research tasks.

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

Execute arbitrary OS commands on the host Ubuntu server. The agent runs under a standard (non-root) user account.

- Run any CLI command (`ls`, `curl`, `git`, `python`, …)
- Install packages via Conda
- Manage tmux sessions for long-running processes

### 🌐 Browser

Headless web browsing for environments without a GUI. Used for web search, page retrieval, form interaction, and scraping.

- Candidate: [agent-browser by Vercel Labs](https://github.com/vercel-labs/agent-browser)
- Operates in headless mode on Ubuntu Server
- Integrates with the agent's tool-calling interface

### 📁 Filesystem

Read, write, list, and manage files on the host OS.

- Create and edit files
- Navigate directories
- Read logs and configuration

### 🔍 Deep Research

Multi-step research workflows combining web search and synthesis.

- Search the web and retrieve pages
- Synthesize results across multiple sources
- Save intermediate findings for iterative analysis

---

## Control Interfaces

### CLI

```bash
python -m agent <command> [args]
```

| Command | Description |
|---|---|
| `run "task"` | Execute a task described in natural language |
| `bot` | Start the Telegram bot (long-polling mode) |
| `status` | Show agent status |
| `logs [N]` | Show last N log entries (default 30) |

**Examples:**

```bash
# Run a task
python -m agent run "find all Python files larger than 1MB"

# Start the Telegram bot
python -m agent bot

# Check status
python -m agent status

# Show last 50 log entries
python -m agent logs 50
```

### Telegram Bot

Start the bot with `python -m agent bot`, then interact via Telegram.

**Commands:**

| Command | Description |
|---|---|
| `/start` | Start the bot / show welcome message |
| `/help` | List available commands and tools |
| `/status` | Show agent status and uptime |
| `/tasks` | List currently running tasks |
| `/logs [N]` | Show last N log entries (default 30) |
| `/exportlogs` | Download full log file |
| `/panic` | 🛑 Emergency halt — immediately kill all agent processes |

Any text message (not a command) is treated as a task for the agent. Tasks run asynchronously — the bot stays responsive while tasks execute, and you can send multiple tasks in parallel.

> Commands are registered with Telegram via `set_my_commands` — they appear in the bot's command menu automatically.

---

## Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for [OpenRouter](https://openrouter.ai) — used during development |
| `TG_BOT_KEY` | Telegram Bot API token (obtained via [@BotFather](https://t.me/BotFather)) |
| `GH_TOKEN` | GitHub token for `git push` and `gh` CLI (optional) |
| `AGENT_MAX_RETRIES` | retries on task failure before giving up (default 3) |

```bash
cp .env.example .env
# fill in OPENROUTER_API_KEY and TG_BOT_KEY
```

### GitHub (git push, gh CLI)

For self-modification with git push and `gh` commands, put your GitHub token in `GHTOKEN.txt` in the project root, or set `GH_TOKEN` in `.env`:

```
# GHTOKEN.txt (one line: the token)
github_pat_xxxx...
```

Or in `.env`:
```
GH_TOKEN=github_pat_xxxx...
```

Run `gh auth setup-git` once so git uses gh for credentials. The agent uses `run_gh` for gh CLI and `git_push` (which passes GH_TOKEN for auth).

---

## Supported LLM Backends

### OpenRouter (default for development)

| Model | OpenRouter ID |
|---|---|
| Qwen 3.5 122B A10B | `qwen/qwen3.5-122b-a10b` |
| GPT OSS 120B | `openai/gpt-oss-120b` |
| Gemini 3 Flash Preview | `google/gemini-3-flash-preview` |

> ⚠️ Do not use expensive flagship models (e.g. GPT-4o, Claude Opus) during development without explicit approval.

### VLLM (local inference)

The agent can be configured to call a locally hosted VLLM endpoint instead of OpenRouter. Set the appropriate base URL in config.

---

## Agent Core

All LLM calls **must** go through the agent core — never call the LLM directly from tools or interfaces. The core is responsible for:

- Routing requests to the configured LLM backend
- Executing tool calls returned by the LLM
- **Logging every tool call** (what tool, what args, what result)

### Tool Call Logging

Every time the LLM invokes a tool, the following is logged:
- Timestamp
- Tool name
- Input arguments
- Output / result
- Any errors

Logs are written to **both**:
1. A local log file (`logs/agent.log`)
2. The Telegram bot (for real-time monitoring)

---

## OS Environment

- **OS:** Ubuntu Server (no GUI, terminal only)
- **Privileges:** No root. Standard user only.
- **Package management:** [Conda](https://docs.conda.io) — install anything in existing or new environments
- **Session management:** [tmux](https://github.com/tmux/tmux) — use for persistent background sessions
- **Browser:** Headless agent-browser (see Tools → Browser)

---

## Safety & Self-Preservation

The agent may receive instructions to modify or rewrite itself. In such cases it **must**:

1. Create a full backup of the current codebase before making changes
2. Apply changes in an isolated copy
3. Validate that the new version runs correctly (start a new instance, run sanity checks)
4. Only replace the running instance after successful validation
5. Never kill the current instance before the new one is confirmed healthy

The `/panic` command exists to interrupt a runaway or stuck agent at any time.

---

## Recommended Stack

| Component | Candidate |
|---|---|
| Agent framework | [pydantic-ai](https://ai.pydantic.dev) or OpenClaw |
| LLM routing | OpenRouter (dev) / VLLM (prod) |
| Telegram interface | [python-telegram-bot](https://python-telegram-bot.org) |
| Browser | [agent-browser (Vercel Labs)](https://github.com/vercel-labs/agent-browser) |
| Session mgmt | tmux |
| Package mgmt | Conda |
| Logging | Python `logging` → file + Telegram |

---

## Getting Started

```bash
# 1. Clone the repo
git clone <repo-url>
cd <repo>

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies (editable + dev tools)
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# fill in OPENROUTER_API_KEY and TG_BOT_KEY

# 5. Run a task via CLI
python -m agent run "hello world"

# 6. Or start the Telegram bot
python -m agent bot
```

---

## Project Structure

```
agent/
├── core/           # LLM orchestration, tool dispatcher, logger
├── tools/          # Individual tools (shell, browser, fs, etc.)
├── interfaces/
│   ├── cli.py      # CLI entrypoint
│   └── telegram.py # Telegram bot
├── config.py       # Env vars and settings
└── __main__.py
logs/
tests/
.env.example
pyproject.toml
README.md
```

---

## Status

🚧 **In active development.** Architecture and tooling decisions are being finalized.
