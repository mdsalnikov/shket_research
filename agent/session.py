"""Session management with SQLite storage - OpenClaw-inspired architecture.

This module provides session persistence using SQLite, following OpenClaw's
session management concepts:
- One session per agent/chat with SQLite persistence
- Conversation history with configurable limits
- Tool call logging and retrieval  
- L0/L1/L2 memory hierarchy for agent memory
- FTS5 for fast text search
- Session isolation per chat_id (DM) or channel

Key concepts from OpenClaw:
- Session key format: agent:<agentId>:<mainKey> (default main)
- dmScope: control DM grouping (main/per-peer/per-channel-peer)
- Memory categories: System, Environment, Skill, Project, Comm, Security

"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import aiosqlite

from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "sessions.db")

# Memory hierarchy levels (inspired by OpenClaw/OpenViking)
MEMORY_L0 = "abstract"  # One-line summary
MEMORY_L1 = "overview"  # Category-based summary (2-3 sentences)
MEMORY_L2 = "details"   # Full content

# Memory categories from OpenClaw
MEMORY_CATEGORIES = ["System", "Environment", "Skill", "Project", "Comm", "Security"]

# Session scopes (OpenClaw dmScope concept)
SCOPE_MAIN = "main"
SCOPE_PER_PEER = "per-peer"
SCOPE_PER_CHANNEL_PEER = "per-channel-peer"


@dataclass
class SessionMessage:
    """A single message in a session.
    
    Supports standard roles (user/assistant/system) and tool calls
    with full parameter and result logging.
    
    """
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_name: str | None = None
    tool_params: dict | None = None
    tool_result: str | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "tool_result": self.tool_result,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMessage":
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            tool_name=data.get("tool_name"),
            tool_params=data.get("tool_params"),
            tool_result=data.get("tool_result"),
            metadata=data.get("metadata"),
        )

    def to_model_message(self) -> dict:
        """Convert to format suitable for LLM context.
        
        Returns a dict compatible with pydantic-ai message format.
        
        """
        msg = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_name:
            msg["tool_name"] = self.tool_name
        if self.tool_params:
            msg["tool_params"] = self.tool_params
        if self.tool_result:
            msg["tool_result"] = self.tool_result
        return msg


@dataclass
class MemoryEntry:
    """Memory entry with L0/L1/L2 hierarchy.
    
    Follows OpenClaw's memory architecture:
    - L0 (abstract): One-line summary for quick scanning
    - L1 (overview): 2-3 sentence overview for context
    - L2 (details): Full content for deep retrieval
    
    Categories: System, Environment, Skill, Project, Comm, Security
    
    """
    key: str              # Unique memory key
    category: str         # One of MEMORY_CATEGORIES
    l0_abstract: str      # One-line summary (required)
    l1_overview: str = "" # 2-3 sentence overview
    l2_details: str = ""  # Full content
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    confidence: float = 1.0
    access_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "category": self.category,
            "l0_abstract": self.l0_abstract,
            "l1_overview": self.l1_overview,
            "l2_details": self.l2_details,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            category=data["category"],
            l0_abstract=data["l0_abstract"],
            l1_overview=data.get("l1_overview", ""),
            l2_details=data.get("l2_details", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            confidence=data.get("confidence", 1.0),
            access_count=data.get("access_count", 0),
        )
