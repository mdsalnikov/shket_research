"""Context compression for handling context overflow errors.

Implements sliding window + summarization approach:
1. Keep recent messages (higher priority)
2. Keep tool calls and their results
3. Summarize older messages
4. Preserve system prompt and memory context
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Result of context compression.
    
    Attributes:
        compressed_history: Compressed conversation history
        removed_count: Number of messages removed
        summary: Summary of removed content (if any)
        compression_ratio: Ratio of original to compressed size
        
    """
    compressed_history: list[dict[str, Any]]
    removed_count: int
    summary: str | None
    compression_ratio: float


class ContextCompressor:
    """Compresses conversation history to fit context window.
    
    Strategy:
    1. Always keep system prompt and memory context
    2. Keep tool calls and their results (high value)
    3. Keep last N messages (recent context)
    4. Summarize older messages into a single context block
    
    Example:
        compressor = ContextCompressor()
        result = compressor.compress(history, target_messages=10)
        compressed_history = result.compressed_history
        
    """
    
    # Default number of recent messages to keep
    DEFAULT_KEEP_RECENT = 10
    
    # Tool calls are valuable - always keep them
    TOOL_ROLES = {"tool", "tool_call"}
    
    def __init__(self, keep_recent: int = DEFAULT_KEEP_RECENT):
        """Initialize compressor.
        
        Args:
            keep_recent: Number of recent messages to always keep
            
        """
        self.keep_recent = keep_recent
    
    def compress(
        self,
        history: list[dict[str, Any]],
        target_messages: int | None = None,
    ) -> CompressionResult:
        """Compress conversation history to target size.
        
        Args:
            history: Full conversation history
            target_messages: Target number of messages (default: keep_recent)
            
        Returns:
            CompressionResult with compressed history and metadata
            
        """
        if not history:
            return CompressionResult(
                compressed_history=[],
                removed_count=0,
                summary=None,
                compression_ratio=1.0,
            )
        
        target = target_messages or self.keep_recent
        
        # If already within target, no compression needed
        if len(history) <= target:
            return CompressionResult(
                compressed_history=history,
                removed_count=0,
                summary=None,
                compression_ratio=1.0,
            )
        
        # Separate messages by priority
        tool_messages = []
        recent_messages = []
        older_messages = []
        
        # Get recent messages (last N)
        recent_start = max(0, len(history) - self.keep_recent)
        recent_messages = history[recent_start:]
        older_messages = history[:recent_start]
        
        # Extract tool calls from older messages
        for msg in older_messages:
            if self._is_tool_message(msg):
                tool_messages.append(msg)
        
        # Create summary of older messages (excluding tools)
        non_tool_older = [m for m in older_messages if not self._is_tool_message(m)]
        summary = self._summarize_messages(non_tool_older) if non_tool_older else None
        
        # Build compressed history
        compressed = []
        
        # Add summary as context if available
        if summary:
            compressed.append({
                "role": "system",
                "content": f"[Previous context summary: {summary}]",
                "metadata": {"compressed": True},
            })
        
        # Add tool messages (they're important for context)
        compressed.extend(tool_messages[-5:])  # Keep last 5 tool messages
        
        # Add recent messages
        compressed.extend(recent_messages)
        
        # Calculate compression ratio
        original_size = sum(len(str(m.get("content", ""))) for m in history)
        compressed_size = sum(len(str(m.get("content", ""))) for m in compressed)
        ratio = original_size / compressed_size if compressed_size > 0 else 1.0
        
        return CompressionResult(
            compressed_history=compressed,
            removed_count=len(history) - len(compressed),
            summary=summary,
            compression_ratio=ratio,
        )
    
    def _is_tool_message(self, message: dict[str, Any]) -> bool:
        """Check if message is a tool call or result.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is tool-related
            
        """
        role = message.get("role", "")
        return role in self.TOOL_ROLES or "tool" in message
    
    def _summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        """Create a brief summary of messages.
        
        For now, uses simple concatenation. In future, could use LLM
        to generate meaningful summary.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary string
            
        """
        if not messages:
            return ""
        
        # Extract key information
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        
        summary_parts = []
        
        if user_messages:
            summary_parts.append(f"{len(user_messages)} user messages")
        
        if assistant_messages:
            summary_parts.append(f"{len(assistant_messages)} assistant responses")
        
        # Get first user message (usually the original task)
        if user_messages:
            first_user = str(user_messages[0].get("content", ""))[:100]
            summary_parts.append(f"Started with: {first_user}...")
        
        return " | ".join(summary_parts)
    
    def estimate_tokens(self, history: list[dict[str, Any]]) -> int:
        """Estimate token count for history.
        
        Simple estimation: ~4 characters per token for English.
        
        Args:
            history: Conversation history
            
        Returns:
            Estimated token count
            
        """
        total_chars = sum(
            len(str(m.get("content", ""))) + len(str(m.get("role", "")))
            for m in history
        )
        return total_chars // 4  # Rough approximation
    
    def needs_compression(
        self,
        history: list[dict[str, Any]],
        max_tokens: int = 100000,
    ) -> bool:
        """Check if history needs compression.
        
        Args:
            history: Conversation history
            max_tokens: Maximum allowed tokens
            
        Returns:
            True if compression is needed
            
        """
        return self.estimate_tokens(history) > max_tokens


async def compress_session_history(
    deps: Any,
    target_messages: int | None = None,
) -> CompressionResult:
    """Compress session history from dependencies.
    
    Convenience function that fetches history from AgentDeps
    and compresses it.
    
    Args:
        deps: AgentDeps instance with get_conversation_history
        target_messages: Target number of messages
        
    Returns:
        CompressionResult with compressed history
        
    """
    history = await deps.get_conversation_history(limit=100)
    compressor = ContextCompressor()
    return compressor.compress(history, target_messages=target_messages)
