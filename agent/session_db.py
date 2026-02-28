"""SessionDB class - SQLite-based session storage following OpenClaw architecture.

This module contains the main SessionDB class separated for clarity.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from typing import Optional

import aiosqlite

from agent.config import PROJECT_ROOT
from agent.session import (
    DEFAULT_DB_PATH,
    MEMORY_CATEGORIES,
    SCOPE_MAIN,
    MemoryEntry,
    SessionMessage,
)

logger = logging.getLogger(__name__)


def _remove_db_files(db_path: str) -> None:
    """Remove database file and WAL/SHM sidecars so a clean DB can be created."""
    for path in (db_path, db_path + "-wal", db_path + "-shm", db_path + "-journal"):
        try:
            if os.path.exists(path):
                os.unlink(path)
                logger.info("Removed %s", path)
        except OSError as e:
            logger.warning("Could not remove %s: %s", path, e)


class SessionDB:
    """SQLite-based session storage following OpenClaw architecture.

    Key features:
    - Persistent session storage with isolation per chat
    - Conversation history with configurable limits
    - Tool call logging with parameters and results
    - L0/L1/L2 memory hierarchy
    - FTS5 full-text search for memory
    - Efficient indexing for fast retrieval

    Usage:
        db = SessionDB()
        await db.init()
        
        # Create/get session
        session_id = await db.get_or_create_session(chat_id=12345)
        
        # Add messages
        await db.add_message(session_id, "user", "Hello!")
        await db.add_message(session_id, "assistant", "Hi there!")
        
        # Get history
        history = await db.get_messages(session_id, limit=20)
        
        # Memory operations
        await db.save_memory(entry)
        results = await db.search_memory("api configuration")

    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def init(self) -> None:
        """Initialize database and create tables.

        If the database is missing or corrupted, removes it and creates a new one.
        Creates all necessary tables and indexes for:
        - sessions: session metadata and routing state
        - messages: conversation history with tool calls
        - memory: L0/L1/L2 hierarchical storage
        - memory_fts: FTS5 virtual table for fast search

        """
        if self._initialized:
            return

        dir_path = os.path.dirname(self.db_path)
        os.makedirs(dir_path, exist_ok=True)

        for attempt in range(2):
            try:
                self._db = await aiosqlite.connect(self.db_path)
                self._db.row_factory = aiosqlite.Row
                await self._db.execute("PRAGMA journal_mode=WAL")
                await self._db.execute("PRAGMA busy_timeout=5000")
                await self._create_tables()
                await self._migrate_sessions_message_history()
                await self._migrate_resumable_tasks()
                self._initialized = True
                logger.info("SessionDB initialized at %s", self.db_path)
                return
            except (sqlite3.Error, OSError) as e:
                if self._db:
                    try:
                        await self._db.close()
                    except Exception:
                        pass
                    self._db = None
                if attempt == 0:
                    logger.warning("Database missing or corrupted (%s), creating new one: %s", type(e).__name__, e)
                    _remove_db_files(self.db_path)
                else:
                    raise

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False

    async def _create_tables(self) -> None:
        """Create necessary tables with OpenClaw-inspired schema."""
        await self._db.executescript("""
            -- Sessions table (OpenClaw session management)
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT UNIQUE NOT NULL,
                chat_id INTEGER,
                agent_id TEXT DEFAULT 'shket',
                scope TEXT DEFAULT 'main',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                message_count INTEGER DEFAULT 0,
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_chat_id ON sessions(chat_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(session_key);

            -- Messages table (conversation history)
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                tool_name TEXT,
                tool_params TEXT,
                tool_result TEXT,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

            -- Memory table (L0/L1/L2 hierarchy from OpenClaw)
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                l0_abstract TEXT NOT NULL,
                l1_overview TEXT,
                l2_details TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                confidence REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category);
            CREATE INDEX IF NOT EXISTS idx_memory_key ON memory(key);

            -- FTS5 for fast text search (OpenClaw-style)
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                key, category, l0_abstract, l1_overview, l2_details,
                content='memory',
                content_rowid='id'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
                INSERT INTO memory_fts(rowid, key, category, l0_abstract, l1_overview, l2_details)
                VALUES (new.id, new.key, new.category, new.l0_abstract, new.l1_overview, new.l2_details);
            END;

            CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, key, category, l0_abstract, l1_overview, l2_details)
                VALUES('delete', old.id, old.key, old.category, old.l0_abstract, old.l1_overview, old.l2_details);
            END;

            CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, key, category, l0_abstract, l1_overview, l2_details)
                VALUES('delete', old.id, old.key, old.category, old.l0_abstract, old.l1_overview, old.l2_details);
                INSERT INTO memory_fts(rowid, key, category, l0_abstract, l1_overview, l2_details)
                VALUES (new.id, new.key, new.category, new.l0_abstract, new.l1_overview, new.l2_details);
            END;
        """)
        await self._db.commit()

    async def _migrate_sessions_message_history(self) -> None:
        """Add message_history_json column to sessions if missing (for pydantic-ai native history)."""
        try:
            await self._db.execute(
                "ALTER TABLE sessions ADD COLUMN message_history_json TEXT"
            )
            await self._db.commit()
            logger.info("Added sessions.message_history_json column")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    async def _migrate_resumable_tasks(self) -> None:
        """Create resumable_tasks table if missing (for resumable/long-running tasks)."""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS resumable_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                resumed_at REAL,
                resume_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_resumable_tasks_status_updated "
            "ON resumable_tasks(status, updated_at)"
        )
        await self._db.commit()
        logger.info("Resumable tasks table ready")

    async def upsert_resumable_task(self, session_id: int, chat_id: int, goal: str) -> int:
        """Set or update resumable task for session to running. Cancel any existing running for this session. Return task id."""
        async with self._lock:
            now = time.time()
            await self._db.execute(
                "UPDATE resumable_tasks SET status = 'cancelled', updated_at = ? WHERE session_id = ? AND status = 'running'",
                (now, session_id),
            )
            await self._db.execute(
                """INSERT INTO resumable_tasks (session_id, chat_id, goal, status, created_at, updated_at, resume_count)
                   VALUES (?, ?, ?, 'running', ?, ?, 0)""",
                (session_id, chat_id, goal, now, now),
            )
            await self._db.commit()
            cursor = await self._db.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_incomplete_resumable_tasks(self) -> list[dict]:
        """Return all rows with status='running', ordered by updated_at."""
        async with self._lock:
            cursor = await self._db.execute(
                """SELECT id, session_id, chat_id, goal, status, created_at, updated_at, resumed_at, resume_count, last_error
                   FROM resumable_tasks WHERE status = 'running' ORDER BY updated_at ASC"""
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_resumable_tasks(
        self, chat_id: int | None = None, limit: int = 20
    ) -> list[dict]:
        """Return recent resumable tasks (any status), optionally for one chat_id, by updated_at DESC."""
        async with self._lock:
            if chat_id is not None:
                cursor = await self._db.execute(
                    """SELECT id, session_id, chat_id, goal, status, created_at, updated_at, resumed_at, resume_count, last_error
                       FROM resumable_tasks WHERE chat_id = ? ORDER BY updated_at DESC LIMIT ?""",
                    (chat_id, limit),
                )
            else:
                cursor = await self._db.execute(
                    """SELECT id, session_id, chat_id, goal, status, created_at, updated_at, resumed_at, resume_count, last_error
                       FROM resumable_tasks ORDER BY updated_at DESC LIMIT ?""",
                    (limit,),
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_resumable_task_by_id(self, task_id: int) -> dict | None:
        """Return one resumable task by id or None."""
        async with self._lock:
            cursor = await self._db.execute(
                """SELECT id, session_id, chat_id, goal, status, created_at, updated_at, resumed_at, resume_count, last_error
                   FROM resumable_tasks WHERE id = ?""",
                (task_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def mark_resumable_task_completed(self, task_id: int) -> None:
        async with self._lock:
            await self._db.execute(
                "UPDATE resumable_tasks SET status = 'completed', updated_at = ? WHERE id = ?",
                (time.time(), task_id),
            )
            await self._db.commit()

    async def mark_resumable_task_failed(self, task_id: int, last_error: str | None = None) -> None:
        async with self._lock:
            await self._db.execute(
                "UPDATE resumable_tasks SET status = 'failed', updated_at = ?, last_error = ? WHERE id = ?",
                (time.time(), last_error, task_id),
            )
            await self._db.commit()

    async def increment_resume_and_set_resumed_at(self, task_id: int) -> None:
        async with self._lock:
            now = time.time()
            await self._db.execute(
                "UPDATE resumable_tasks SET resume_count = resume_count + 1, resumed_at = ?, updated_at = ? WHERE id = ?",
                (now, now, task_id),
            )
            await self._db.commit()

    async def get_model_message_history(self, session_id: int) -> str | None:
        """Get stored pydantic-ai message history (JSON) for this session."""
        async with self._lock:
            try:
                cursor = await self._db.execute(
                    "SELECT message_history_json FROM sessions WHERE id = ?",
                    (session_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    return None
                return row["message_history_json"]
            except (sqlite3.OperationalError, KeyError, IndexError):
                return None

    async def set_model_message_history(self, session_id: int, json_str: str) -> None:
        """Store pydantic-ai message history (JSON) for this session."""
        async with self._lock:
            await self._db.execute(
                "UPDATE sessions SET message_history_json = ?, updated_at = ? WHERE id = ?",
                (json_str, time.time(), session_id),
            )
            await self._db.commit()

    def _session_key(
        self, 
        chat_id: int, 
        scope: str = SCOPE_MAIN,
        agent_id: str = "shket"
    ) -> str:
        """Generate session key in OpenClaw format.

        Format: agent:<agentId>:<scope>:<chatId>
        - agent:shket:main:12345
        - agent:shket:per-peer:12345

        """
        return f"agent:{agent_id}:{scope}:{chat_id}"

    async def get_or_create_session(
        self, 
        chat_id: int, 
        scope: str = SCOPE_MAIN,
        agent_id: str = "shket"
    ) -> int:
        """Get or create a session for the given chat_id.

        Args:
            chat_id: Telegram chat ID
            scope: Session scope (main/per-peer/per-channel-peer)
            agent_id: Agent identifier
            
        Returns:
            Session ID (integer primary key)

        """
        session_key = self._session_key(chat_id, scope, agent_id)
        now = time.time()

        async with self._lock:
            cursor = await self._db.execute(
                "SELECT id FROM sessions WHERE session_key = ?", (session_key,)
            )
            row = await cursor.fetchone()
            if row:
                return row["id"]

            # Create new session
            await self._db.execute(
                """INSERT INTO sessions (session_key, chat_id, agent_id, scope, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_key, chat_id, agent_id, scope, now, now),
            )
            await self._db.commit()

            cursor = await self._db.execute(
                "SELECT id FROM sessions WHERE session_key = ?", (session_key,)
            )
            row = await cursor.fetchone()
            return row["id"]

    async def get_session(self, session_id: int) -> dict | None:
        """Get session metadata by ID."""
        async with self._lock:
            cursor = await self._db.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_params: dict | None = None,
        tool_result: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Add a message to a session.

        Args:
            session_id: Session ID from get_or_create_session
            role: Message role (user/assistant/system/tool)
            content: Message content
            tool_name: Tool name if role="tool"
            tool_params: Tool parameters dict
            tool_result: Tool result string
            metadata: Additional metadata dict
            
        Returns:
            Message ID (integer primary key)

        """
        now = time.time()
        tool_params_json = json.dumps(tool_params) if tool_params else None
        metadata_json = json.dumps(metadata) if metadata else None

        async with self._lock:
            cursor = await self._db.execute(
                """INSERT INTO messages 
                   (session_id, role, content, timestamp, tool_name, tool_params, tool_result, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, role, content, now, tool_name, tool_params_json, tool_result, metadata_json),
            )
            # Update session updated_at and message_count
            await self._db.execute(
                """UPDATE sessions 
                   SET updated_at = ?, message_count = message_count + 1
                   WHERE id = ?""",
                (now, session_id),
            )
            await self._db.commit()
            return cursor.lastrowid

    async def get_messages(
        self, 
        session_id: int, 
        limit: int = 50,
        offset: int = 0
    ) -> list[SessionMessage]:
        """Get messages from a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            List of SessionMessage objects (oldest first)

        """
        async with self._lock:
            cursor = await self._db.execute(
                """SELECT * FROM messages 
                   WHERE session_id = ? 
                   ORDER BY timestamp ASC 
                   LIMIT ? OFFSET ?""",
                (session_id, limit, offset),
            )
            rows = await cursor.fetchall()

            messages = []
            for row in rows:
                tool_params = json.loads(row["tool_params"]) if row["tool_params"] else None
                metadata = json.loads(row["metadata"]) if row["metadata"] else None
                messages.append(SessionMessage(
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    tool_name=row["tool_name"],
                    tool_params=tool_params,
                    tool_result=row["tool_result"],
                    metadata=metadata,
                ))
            return messages

    async def get_recent_messages(
        self, 
        session_id: int, 
        limit: int = 20
    ) -> list[SessionMessage]:
        """Get most recent messages from a session (newest first).

        This is useful for building LLM context where you want the
        most recent messages.

        Args:
            session_id: Session ID
            limit: Maximum number of messages
            
        Returns:
            List of SessionMessage objects (newest first)

        """
        async with self._lock:
            cursor = await self._db.execute(
                """SELECT * FROM messages 
                   WHERE session_id = ? 
                   ORDER BY timestamp DESC 
                   LIMIT ?""",
                (session_id, limit),
            )
            rows = await cursor.fetchall()

            messages = []
            for row in rows:
                tool_params = json.loads(row["tool_params"]) if row["tool_params"] else None
                metadata = json.loads(row["metadata"]) if row["metadata"] else None
                messages.append(SessionMessage(
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    tool_name=row["tool_name"],
                    tool_params=tool_params,
                    tool_result=row["tool_result"],
                    metadata=metadata,
                ))
            # Reverse to get chronological order
            return list(reversed(messages))

    async def get_conversation_history(
        self, 
        session_id: int,
        limit: int = 20
    ) -> list[dict]:
        """Get conversation history in format suitable for LLM context.

        Returns messages in chronological order with role and content,
        suitable for passing to pydantic-ai as message history.

        Args:
            session_id: Session ID
            limit: Maximum number of messages
            
        Returns:
            List of dicts with 'role' and 'content' keys

        """
        messages = await self.get_recent_messages(session_id, limit)
        return [msg.to_model_message() for msg in messages]

    async def clear_session(self, session_id: int) -> None:
        """Clear all messages from a session.

        Keeps the session metadata but removes all messages.

        """
        async with self._lock:
            await self._db.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,)
            )
            await self._db.execute(
                "UPDATE sessions SET message_count = 0, updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )
            await self._db.commit()


    async def get_session_stats(
        self, 
        session_id: int,
        include_last_messages: int = 5
    ) -> dict:
        """Get session statistics including message count and estimated tokens.

        Args:
            session_id: Session ID
            include_last_messages: Number of last messages to include in stats
            
        Returns:
            Dict with:
            - session_id: int
            - message_count: int
            - created_at: str (ISO format)
            - updated_at: str (ISO format)
            - uptime_seconds: float
            - estimated_tokens: int
            - last_messages: list[dict] (preview of last messages)

        """
        from datetime import datetime
        
        # Get session metadata
        session = await self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # Get recent messages for token estimation
        messages = await self.get_recent_messages(session_id, limit=100)
        
        # Estimate tokens (rough: ~4 chars per token for English, ~2 for Russian)
        total_chars = sum(len(m.content) for m in messages)
        # Conservative estimate: 3 chars per token (mixed content)
        estimated_tokens = total_chars // 3
        
        # Get last messages preview
        last_messages = []
        for msg in messages[-include_last_messages:]:
            last_messages.append({
                "role": msg.role,
                "content_preview": msg.content[:100] + ("..." if len(msg.content) > 100 else ""),
                "chars": len(msg.content),
            })
        
        created_at = datetime.fromtimestamp(session["created_at"])
        updated_at = datetime.fromtimestamp(session["updated_at"])
        now = datetime.now()
        
        return {
            "session_id": session_id,
            "chat_id": session.get("chat_id"),
            "message_count": session.get("message_count", 0),
            "created_at": created_at.isoformat(timespec="seconds"),
            "updated_at": updated_at.isoformat(timespec="seconds"),
            "uptime_seconds": (now - created_at).total_seconds(),
            "idle_seconds": (now - updated_at).total_seconds(),
            "estimated_tokens": estimated_tokens,
            "total_chars": total_chars,
            "last_messages": last_messages,
        }

    # ============ Memory Operations ============
    # ============ Memory Operations ============

    async def save_memory(self, entry: MemoryEntry) -> None:
        """Save or update a memory entry.

        Uses UPSERT semantics - updates if key exists, inserts otherwise.
        Updates the updated_at timestamp on modification.

        Args:
            entry: MemoryEntry object to save

        """
        now = time.time()
        async with self._lock:
            await self._db.execute(
                """INSERT INTO memory 
                   (key, category, l0_abstract, l1_overview, l2_details, created_at, updated_at, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       category = excluded.category,
                       l0_abstract = excluded.l0_abstract,
                       l1_overview = excluded.l1_overview,
                       l2_details = excluded.l2_details,
                       updated_at = excluded.updated_at,
                       confidence = excluded.confidence""",
                (entry.key, entry.category, entry.l0_abstract, entry.l1_overview, 
                 entry.l2_details, now, now, entry.confidence),
            )
            await self._db.commit()

    async def get_memory(self, key: str) -> MemoryEntry | None:
        """Get a memory entry by key.

        Increments access_count on retrieval (for popularity tracking).

        Args:
            key: Memory key to retrieve
            
        Returns:
            MemoryEntry if found, None otherwise

        """
        # Increment access count
        await self._db.execute(
            "UPDATE memory SET access_count = access_count + 1 WHERE key = ?",
            (key,),
        )
        await self._db.commit()

        cursor = await self._db.execute(
            "SELECT * FROM memory WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        return MemoryEntry(
            key=row["key"],
            category=row["category"],
            l0_abstract=row["l0_abstract"],
            l1_overview=row["l1_overview"] or "",
            l2_details=row["l2_details"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            confidence=row["confidence"],
            access_count=row["access_count"],
        )

    async def search_memory(
        self, 
        query: str, 
        category: str | None = None,
        limit: int = 10
    ) -> list[MemoryEntry]:
        """Search memory using FTS5 full-text search.

        Args:
            query: Search query (supports FTS5 syntax)
            category: Optional category filter
            limit: Maximum results to return
            
        Returns:
            List of matching MemoryEntry objects

        """
        # Use FTS5 for fast search
        if category:
            cursor = await self._db.execute(
                """SELECT m.* FROM memory m
                   JOIN memory_fts fts ON m.id = fts.rowid
                   WHERE memory_fts MATCH ? AND m.category = ?
                   ORDER BY m.confidence DESC, m.access_count DESC
                   LIMIT ?""",
                (query, category, limit),
            )
        else:
            cursor = await self._db.execute(
                """SELECT m.* FROM memory m
                   JOIN memory_fts fts ON m.id = fts.rowid
                   WHERE memory_fts MATCH ?
                   ORDER BY m.confidence DESC, m.access_count DESC
                   LIMIT ?""",
                (query, limit),
            )

        rows = await cursor.fetchall()
        entries = []
        for row in rows:
            entries.append(MemoryEntry(
                key=row["key"],
                category=row["category"],
                l0_abstract=row["l0_abstract"],
                l1_overview=row["l1_overview"] or "",
                l2_details=row["l2_details"] or "",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                confidence=row["confidence"],
                access_count=row["access_count"],
            ))
        return entries

    async def get_l0_overview(self) -> dict[str, list[str]]:
        """Get L0 abstracts grouped by category.

        This provides a quick scan of all memory, useful for
        context injection without consuming too many tokens.

        Returns:
            Dict mapping category -> list of L0 abstracts

        """
        cursor = await self._db.execute(
            """SELECT category, l0_abstract FROM memory 
               ORDER BY category, confidence DESC"""
        )
        rows = await cursor.fetchall()

        overview: dict[str, list[str]] = {}
        for row in rows:
            cat = row["category"]
            if cat not in overview:
                overview[cat] = []
            overview[cat].append(row["l0_abstract"])

        return overview

    async def get_context_summary(self) -> str:
        """Get L0 memory summary as a formatted string for context injection.

        Returns:
            Formatted string with categories and L0 abstracts, or "" if no memory.
        """
        overview = await self.get_l0_overview()
        if not overview:
            return ""
        lines = []
        for category in sorted(overview.keys()):
            lines.append(f"## {category}")
            for abstract in overview[category]:
                lines.append(f"- {abstract}")
            lines.append("")
        return "\n".join(lines).strip()

    async def delete_memory(self, key: str) -> bool:
        """Delete a memory entry by key.

        Args:
            key: Memory key to delete
            
        Returns:
            True if deleted, False if not found

        """
        async with self._lock:
            cursor = await self._db.execute(
                "DELETE FROM memory WHERE key = ?", (key,)
            )
            await self._db.commit()
            return cursor.rowcount > 0

    async def get_all_categories(self) -> list[str]:
        """Get all memory categories in use."""
        cursor = await self._db.execute(
            "SELECT DISTINCT category FROM memory ORDER BY category"
        )
        rows = await cursor.fetchall()
        return [row["category"] for row in rows]
