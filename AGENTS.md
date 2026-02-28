# Shket Research Agent

Autonomous LLM-powered agent for executing tasks on an Ubuntu server. See `README.md` for architecture and full documentation.

## Cursor Cloud specific instructions

- **Runtime:** Python 3.11 in a virtualenv at `.venv/`. Activate with `source .venv/bin/activate`.
- **Lint:** `ruff check .` (config in `pyproject.toml`)
- **Test (unit):** `pytest tests/test_cli.py -v`
- **Test (agent, requires OPENROUTER_API_KEY):** `pytest tests/test_agent_capabilities.py -v` — 5 tests calling GPT-OSS-120B via OpenRouter. Takes ~10s.
- **Run CLI:** `python -m agent run "your task"` — calls the LLM and uses tools (shell, filesystem, web_search).
- **Run TG bot:** `python -m agent bot` — starts long-polling. Requires `TG_BOT_KEY` env var.
- **Default model:** vLLM: `Qwen/Qwen3.5-122B-A10B-FP8` (set `VLLM_MODEL_NAME`); OpenRouter: `openai/gpt-oss-120b`. Override with `AGENT_MODEL` env var.
- **Environment variables:** `OPENROUTER_API_KEY` (required for LLM), `TG_BOT_KEY` (required for bot), `AGENT_MODEL` (optional override).
- **Tools:** `run_shell` (OS commands, 30s timeout), `read_file`/`write_file`/`list_dir` (sandboxed to /workspace), `web_search` (DuckDuckGo HTML).
