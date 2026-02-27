# 🤖 Shket Research Agent

Autonomous LLM-powered agent for executing tasks on an Ubuntu server — controllable via CLI and Telegram bot.

---

## Overview

OpenAgent is a self-sufficient AI agent built around a central orchestration core. It accepts commands through a CLI or a Telegram bot, executes arbitrary tasks on the host OS, and logs every action it takes. The agent is designed for research workflows, including web browsing, code execution, environment management, and deep research tasks.

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

## Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for [OpenRouter](https://openrouter.ai) — used during development |
| `TG_BOT_KEY` | Telegram Bot API token (obtained via [@BotFather](https://t.me/BotFather)) |

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

`.env.example`:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
TG_BOT_KEY=your_telegram_bot_token_here
```

---

## Supported LLM Backends

### OpenRouter (default for development)

The following models are approved for use (balance cost vs. capability):

| Model | OpenRouter ID |
|---|---|
| Qwen 3.5 122B A10B | `qwen/qwen3.5-122b-a10b` |
| GPT OSS 120B | `openai/gpt-oss-120b` |
| Gemini 3 Flash Preview | `google/gemini-3-flash-preview` |

> ⚠️ Do not use expensive flagship models (e.g. GPT-4o, Claude Opus) during development without explicit approval.

### VLLM (local inference)

The agent can be configured to call a locally hosted VLLM endpoint instead of OpenRouter. Set the appropriate base URL in config.

---

## Control Interfaces

### CLI

Run the agent directly from the terminal:

```bash
python -m agent run "your task here"
```

### Telegram Bot

Send commands to the agent via the configured Telegram bot. All agent output and logs are also sent back through the bot.

**Special system commands:**

| Command | Description |
|---|---|
| `/panic` | Immediately halt all current agent processes |

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
- **Browser:** Headless agent-browser (see below)

---

## Web / Browser

Since there is no GUI, a CLI-compatible browser agent is used. Candidate: **[agent-browser by Vercel Labs](https://github.com/vercel-labs/agent-browser)**.

**Decision required:** evaluate `agent-browser` (and alternatives) for:
- Headless compatibility on Ubuntu Server
- Integration with the tool-calling interface
- Reliability for search and page fetching tasks

---

## Deep Research

Deep research is a first-class use case. The agent should support multi-step research workflows including:

- Web search and page retrieval
- Synthesizing results across multiple sources
- Saving intermediate findings

> Implementation details TBD — will be defined in a follow-up design doc.

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

# 2. Create conda environment
conda create -n agent python=3.11
conda activate agent

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# fill in OPENROUTER_API_KEY and TG_BOT_KEY

# 5. Run
python -m agent run "hello world"
```

---

## Project Structure (planned)

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
.env.example
README.md
```

---

## Status

🚧 **In active development.** Architecture and tooling decisions are being finalized.
