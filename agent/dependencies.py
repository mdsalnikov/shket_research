"""Pydantic AI dependencies for session management.

This module defines the dependency injection system for the agent,
integrating SQLite sessions with Pydantic AI's RunContext.

Based on OpenClaw's session concept and Pydantic AI's dependency system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunContext

from agent.config import DEFAULT_MODEL, OPENROUTER_API_KEY
from agent.session_db import SessionDB
from agent.session import SessionMessage, MemoryEntry, MEMORY_CATEGORIES
from agent.session_globals import get_db

logger = logging.getLogger(__name__)


@dataclass
class AgentDeps:
    """Dependencies passed to the agent at runtime.

    This dataclass holds all the runtime context needed by tools,
    system prompts, and output validators.

    Inspired by OpenClaw's session management with SQLite persistence.
    
    Attributes:
        db: SessionDB instance for session/memory operations
        session_id: Current session ID (SQLite primary key)
        chat_id: Telegram chat ID for session isolation
        model_name: Model identifier for LLM calls
        api_key: OpenRouter API key
        user_id: Telegram user ID (optional)
        username: Telegram username (optional)
        session_scope: Session scope for isolation (main/per-peer/per-channel-peer)
        message_count: Number of messages in current session
        current_task: Current task description (runtime state)
        retry_count: Number of retry attempts (runtime state)
        last_error: Last error message (runtime state)

    """

    # Session management
    db: SessionDB
    session_id: int
    chat_id: int

    # Configuration
    model_name: str = DEFAULT_MODEL
    api_key: str = ""

    # User context
    user_id: int | None = None
    username: str | None = None

    # Session metadata
    session_scope: str = "main"  # For per-channel isolation (OpenClaw dmScope)
    message_count: int = 0

    # Runtime state (not persisted)
    current_task: str | None = None
    retry_count: int = 0
    last_error: str | None = None

    def __post_init__(self):
        """Set default API key if not provided."""
        if not self.api_key:
            self.api_key = OPENROUTER_API_KEY

    @classmethod
    async def create(cls, chat_id: int, **kwargs) -> "AgentDeps":
        """Factory method to create dependencies with database initialization.
        
        This is the preferred way to create AgentDeps instances.
        It ensures the database is initialized and a session is created.
        
        Args:
            chat_id: Telegram chat ID for session isolation
            **kwargs: Additional arguments to pass to AgentDeps constructor
            
        Returns:
            Initialized AgentDeps instance with active session
            
        """
        db = await get_db()
        scope = kwargs.pop("session_scope", "main")
        session_id = await db.get_or_create_session(chat_id, scope=scope)
        
        # Get session metadata
        session_data = await db.get_session(session_id)
        message_count = session_data.get("message_count", 0) if session_data else 0
        
        return cls(
            db=db,
            session_id=session_id,
            chat_id=chat_id,
            session_scope=scope,
            message_count=message_count,
            **kwargs,
        )

    # ============ Message Operations ============

    async def add_user_message(self, content: str, metadata: dict | None = None) -> int:
        """Add a user message to the session.
        
        Args:
            content: Message content
            metadata: Optional metadata dict
            
        Returns:
            Message ID
            
        """
        return await self.db.add_message(
            self.session_id,
            role="user",
            content=content,
            metadata=metadata,
        )

    async def add_assistant_message(self, content: str, metadata: dict | None = None) -> int:
        """Add an assistant message to the session.
        
        Args:
            content: Message content
            metadata: Optional metadata dict
            
        Returns:
            Message ID
            
        """
        return await self.db.add_message(
            self.session_id,
            role="assistant",
            content=content,
            metadata=metadata,
        )

    async def add_tool_call(
        self,
        tool_name: str,
        params: dict | None,
        result: str | None,
        content: str = "",
    ) -> int:
        """Add a tool call to the session.
        
        Args:
            tool_name: Name of the tool called
            params: Tool parameters
            result: Tool result
            content: Optional content/message
            
        Returns:
            Message ID
            
        """
        return await self.db.add_message(
            self.session_id,
            role="tool",
            content=content,
            tool_name=tool_name,
            tool_params=params,
            tool_result=result,
        )

    async def get_history(self, limit: int = 20) -> list[SessionMessage]:
        """Get recent conversation history.
        
        Args:
            limit: Maximum number of messages
            
        Returns:
            List of SessionMessage objects (oldest first)
            
        """
        return await self.db.get_recent_messages(self.session_id, limit=limit)

    async def get_conversation_history(self, limit: int = 20) -> list[dict]:
        """Get conversation history in LLM-compatible format.
        
        Args:
            limit: Maximum number of messages
            
        Returns:
            List of dicts with 'role' and 'content' keys
            
        """
        return await self.db.get_conversation_history(self.session_id, limit=limit)

    # ============ Memory Operations ============

    async def save_memory(
        self,
        key: str,
        category: str,
        l0_abstract: str,
        l1_overview: str = "",
        l2_details: str = "",
        confidence: float = 1.0,
    ) -> None:
        """Save a memory entry.
        
        Args:
            key: Unique memory key
            category: Memory category (System, Environment, Skill, Project, Comm, Security)
            l0_abstract: One-line summary
            l1_overview: 2-3 sentence overview
            l2_details: Full details
            confidence: Confidence level (0.0-1.0)
            
        """
        if category not in MEMORY_CATEGORIES:
            logger.warning(f"Invalid memory category: {category}, using 'Project'")
            category = "Project"
            
        entry = MemoryEntry(
            key=key,
            category=category,
            l0_abstract=l0_abstract,
            l1_overview=l1_overview,
            l2_details=l2_details,
            confidence=confidence,
        )
        await self.db.save_memory(entry)

    async def recall_memory(self, key: str) -> MemoryEntry | None:
        """Recall a memory entry by key.
        
        Args:
            key: Memory key to retrieve
            
        Returns:
            MemoryEntry if found, None otherwise
            
        """
        return await self.db.get_memory(key)

    async def search_memory(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search memory for relevant information.
        
        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results
            
        Returns:
            List of matching MemoryEntry objects
            
        """
        return await self.db.search_memory(query, category=category, limit=limit)

    async def get_context_summary(self) -> str:
        """Get L0/L1 memory summary for context injection.
        
        This provides a quick overview of all memory, useful for
        system prompt context injection.
        
        Returns:
            Formatted memory summary string
            
        """
        # Get L0 overview (quick scan)
        l0 = await self.db.get_l0_overview()

        if not l0:
            return ""

        lines = ["## Memory Context (L0)"]
        for category, summaries in l0.items():
            lines.append(f"\n### {category}")
            for summary in summaries[:5]:  # Limit per category
                lines.append(f"- {summary}")

        return "\n".join(lines)

    async def delete_memory(self, key: str) -> bool:
        """Delete a memory entry.
        
        Args:
            key: Memory key to delete
            
        Returns:
            True if deleted, False if not found
            
        """
        return await self.db.delete_memory(key)


# Type alias for run context
DepsContext = RunContext[AgentDeps]


# System prompt generator that includes memory context
async def get_system_prompt_with_memory(ctx: DepsContext) -> str:
    """Generate system prompt with injected memory context.
    
    Args:
        ctx: RunContext with AgentDeps
        
    Returns:
        System prompt string with memory context appended
        
    """
    from agent.core.agent import SYSTEM_PROMPT

    # Get memory context
    memory_context = await ctx.deps.get_context_summary()

    if memory_context:
        return f"{SYSTEM_PROMPT}\n\n{memory_context}"

    return SYSTEM_PROMPT


# Tool context helpers
def get_deps(ctx: RunContext[AgentDeps]) -> AgentDeps:
    """Extract dependencies from run context.
    
    Args:
        ctx: RunContext with AgentDeps
        
    Returns:
        AgentDeps instance
        
    """
    return ctx.deps


async def log_tool_call(
    ctx: RunContext[AgentDeps], 
    tool_name: str, 
    params: dict | None = None,
    result: str | None = None,
) -> None:
    """Log a tool call to the session.
    
    Args:
        ctx: RunContext with AgentDeps
        tool_name: Name of the tool
        params: Tool parameters
        result: Tool result
        
    """
    await ctx.deps.add_tool_call(tool_name, params, result)
