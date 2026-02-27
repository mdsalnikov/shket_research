"""Global session database instance and helper functions.

Provides singleton access to SessionDB following OpenClaw's architecture.
"""

from __future__ import annotations

import logging

from agent.session_db import SessionDB, DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

# Global singleton instance
_db_instance: SessionDB | None = None


async def get_db() -> SessionDB:
    """Get or create the global SessionDB instance.
    
    This follows the singleton pattern to ensure only one database
    connection exists throughout the application lifecycle.
    
    Returns:
        SessionDB instance (initialized)
    
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = SessionDB(DEFAULT_DB_PATH)
        await _db_instance.init()
    return _db_instance


async def close_db() -> None:
    """Close the global database connection.
    
    Should be called on application shutdown.
    
    """
    global _db_instance
    if _db_instance is not None:
        await _db_instance.close()
        _db_instance = None
        logger.info("SessionDB connection closed")


async def reset_db() -> None:
    """Reset the global database instance.
    
    Useful for testing - closes the current connection and
    removes the singleton so a fresh one will be created.
    
    """
    await close_db()
