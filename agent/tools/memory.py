"""Memory tools for the agent.

These tools allow the agent to store and recall information across sessions,
using the SQLite-based memory system with L0/L1/L2 hierarchy.
"""

from __future__ import annotations

import logging

from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


async def recall(
    ctx: RunContext,
    query: str,
    category: str | None = None,
) -> str:
    """Recall information from memory.

    Search the agent's long-term memory for relevant information.
    Memory is organized by categories and uses L0/L1/L2 hierarchy:
    - L0: Quick abstract (one-line summary)
    - L1: Category overview (2-3 sentences)
    - L2: Full details (complete information)

    Args:
        query: Search query (keyword or phrase)
        category: Optional category filter (System, Environment, Skill, Project, Comm, Security)

    Returns:
        Matching memory entries with L1 overview and L2 details if relevant.
    """
    try:
        # Check if deps has memory methods (session mode)
        if hasattr(ctx.deps, "search_memory"):
            entries = await ctx.deps.search_memory(query, category=category)

            if not entries:
                return f"No memory found for query: {query}"

            # Format results
            lines = [f"Found {len(entries)} memory entries:\n"]
            for entry in entries[:5]:  # Limit to top 5
                lines.append(f"**[{entry.key}]** ({entry.category})")
                lines.append(f"L0: {entry.l0_abstract}")
                if entry.l1_overview:
                    lines.append(f"L1: {entry.l1_overview}")
                lines.append("")

                # Include L2 details for top result only
                if entry == entries[0] and entry.l2_details:
                    lines.append("Full details:")
                    lines.append(entry.l2_details)
                    lines.append("")

            return "\n".join(lines)
        else:
            # Legacy mode - no session support
            return f"Memory search not available (no session). Query: {query}"

    except Exception as e:
        logger.error("Memory recall failed: %s", e)
        return f"Error recalling memory: {e}"


async def remember(
    ctx: RunContext,
    key: str,
    category: str,
    abstract: str,
    overview: str = "",
    details: str = "",
    confidence: float = 1.0,
) -> str:
    """Save important information to long-term memory.

    Store information that should persist across sessions.
    Memory entries are organized with L0/L1/L2 hierarchy:

    Args:
        key: Unique identifier for this memory (e.g., "project_status", "api_config")
        category: One of: System, Environment, Skill, Project, Comm, Security
        abstract: L0 - One-line summary (required)
        overview: L1 - 2-3 sentence overview (optional)
        details: L2 - Full detailed information (optional)
        confidence: Confidence level 0.0-1.0 (default 1.0)

    Returns:
        Confirmation message.
    """
    # Validate category
    valid_categories = ["System", "Environment", "Skill", "Project", "Comm", "Security"]
    if category not in valid_categories:
        return f"Invalid category '{category}'. Must be one of: {', '.join(valid_categories)}"

    try:
        # Check if deps has memory methods (session mode)
        if hasattr(ctx.deps, "save_memory"):
            await ctx.deps.save_memory(
                key=key,
                category=category,
                l0_abstract=abstract,
                l1_overview=overview,
                l2_details=details,
                confidence=confidence,
            )

            logger.info("Saved memory: %s (%s)", key, category)
            return f"✅ Remembered: [{key}] {abstract}"
        else:
            # Legacy mode - no session support
            return f"Memory not available (no session). Would have saved: [{key}] {abstract}"

    except Exception as e:
        logger.error("Memory save failed: %s", e)
        return f"Error saving memory: {e}"


# Tool metadata for Pydantic AI
recall.__doc__ = recall.__doc__ or ""
remember.__doc__ = remember.__doc__ or ""
