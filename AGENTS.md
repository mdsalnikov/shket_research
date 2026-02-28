# Shket Research Agent

Autonomous LLM-powered agent for executing tasks on an Ubuntu server. See `README.md` for architecture and full documentation.

## Cursor Cloud specific instructions

- **Runtime:** Python 3.11 in a virtualenv at `.venv/`. Activate with `source .venv/bin/activate`.
- **Lint:** `ruff check .` (config in `pyproject.toml`)
- **Test (unit):** `pytest tests/test_cli.py -v`
- **Test (agent):** `USE_VLLM=1 pytest tests/test_agent_capabilities.py -v` (local vLLM) or with `OPENROUTER_API_KEY` for OpenRouter.
- **Run CLI:** `python -m agent run "your task"` — calls the LLM and uses tools (shell, filesystem, web_search).
- **Run TG bot:** `python -m agent bot` — starts long-polling. Requires `TG_BOT_KEY` env var.
- **Default model:** vLLM `Qwen/Qwen3.5-27B` (local). OpenRouter override: `OPENROUTER_MODEL_NAME`, or `AGENT_MODEL` for both.
- **Environment variables:** `TG_BOT_KEY` (bot), `OPENROUTER_API_KEY` (cloud), `VLLM_MODEL_NAME` (local default Qwen/Qwen3.5-27B).
- **Tools:** `run_shell` (OS commands, 30s timeout), `read_file`/`write_file`/`list_dir` (sandboxed to /workspace), `web_search` (DuckDuckGo HTML).
