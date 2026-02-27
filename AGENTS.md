# Shket Research Agent

Autonomous LLM-powered agent for executing tasks on an Ubuntu server. See `README.md` for architecture and full documentation.

## Cursor Cloud specific instructions

- **Runtime:** Python 3.11 in a virtualenv at `.venv/`. Activate with `source .venv/bin/activate`.
- **Lint:** `ruff check .` (config in `pyproject.toml`)
- **Test:** `pytest -v` (tests in `tests/`)
- **Run CLI:** `python -m agent run "your task"` (see README "Getting Started")
- **Run TG bot:** `python -m agent bot` — starts long-polling. Requires `TG_BOT_KEY` env var. Supports `/start`, `/panic`, and free-text messages.
- **Environment variables:** Copy `.env.example` to `.env` and fill in `OPENROUTER_API_KEY` and `TG_BOT_KEY`. The agent needs `OPENROUTER_API_KEY` to make LLM calls; the Telegram bot needs `TG_BOT_KEY`.
- **Status:** The project is in early scaffold stage — the agent core and tools are not yet implemented. CLI and Telegram bot entrypoints are in place.
