"""Shket Research Agent — autonomous LLM agent for Ubuntu server.

This agent features:
- SQLite-based session persistence (OpenClaw-inspired)
- L0/L1/L2 memory hierarchy
- Pydantic AI integration with dependency injection
- Multi-channel support (CLI, Telegram)
"""

from agent.config import VERSION

__all__ = ["VERSION"]
