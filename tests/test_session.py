"""Tests for session management with OpenClaw-inspired architecture."""

import asyncio
import os
import tempfile
import pytest

from agent.session import SessionMessage, MemoryEntry, MEMORY_CATEGORIES
from agent.session_db import SessionDB


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
async def session_db(temp_db):
    """Create and initialize a SessionDB instance."""
    db = SessionDB(temp_db)
    await db.init()
    yield db
    await db.close()


# ============ Session Tests ============

@pytest.mark.asyncio
async def test_session_creation(session_db):
    """Test creating a session."""
    session_id = await session_db.get_or_create_session(12345)
    assert session_id > 0

    # Calling again should return same session
    session_id2 = await session_db.get_or_create_session(12345)
    assert session_id2 == session_id


@pytest.mark.asyncio
async def test_session_key_format(session_db):
    """Test OpenClaw-style session key format."""
    session_id = await session_db.get_or_create_session(12345, scope="main", agent_id="shket")
    session = await session_db.get_session(session_id)
    
    assert session is not None
    assert session["session_key"] == "agent:shket:main:12345"
    assert session["agent_id"] == "shket"
    assert session["scope"] == "main"


@pytest.mark.asyncio
async def test_session_scopes(session_db):
    """Test different session scopes (OpenClaw dmScope concept)."""
    # Main scope
    session_main = await session_db.get_or_create_session(12345, scope="main")
    
    # Per-peer scope
    session_peer = await session_db.get_or_create_session(12345, scope="per-peer")
    
    # Should be different sessions
    assert session_main != session_peer
    
    # Verify keys
    main_data = await session_db.get_session(session_main)
    peer_data = await session_db.get_session(session_peer)
    
    assert "main" in main_data["session_key"]
    assert "per-peer" in peer_data["session_key"]


@pytest.mark.asyncio
async def test_add_message(session_db):
    """Test adding messages to a session."""
    session_id = await session_db.get_or_create_session(12345)

    msg_id = await session_db.add_message(
        session_id,
        role="user",
        content="Hello, agent!",
    )
    assert msg_id > 0

    msg_id2 = await session_db.add_message(
        session_id,
        role="assistant",
        content="Hello! How can I help?",
    )
    assert msg_id2 > msg_id


@pytest.mark.asyncio
async def test_get_messages(session_db):
    """Test retrieving messages from a session."""
    session_id = await session_db.get_or_create_session(12345)

    await session_db.add_message(session_id, "user", "Message 1")
    await session_db.add_message(session_id, "assistant", "Message 2")
    await session_db.add_message(session_id, "user", "Message 3")

    messages = await session_db.get_messages(session_id)
    assert len(messages) == 3
    assert messages[0].content == "Message 1"
    assert messages[1].content == "Message 2"
    assert messages[2].content == "Message 3"


@pytest.mark.asyncio
async def test_get_messages_limit(session_db):
    """Test message limit."""
    session_id = await session_db.get_or_create_session(12345)

    for i in range(10):
        await session_db.add_message(session_id, "user", f"Message {i}")

    messages = await session_db.get_messages(session_id, limit=5)
    assert len(messages) == 5


@pytest.mark.asyncio
async def test_get_recent_messages(session_db):
    """Test getting recent messages in reverse order."""
    session_id = await session_db.get_or_create_session(12345)

    for i in range(5):
        await session_db.add_message(session_id, "user", f"Message {i}")

    # Get recent (should be in chronological order)
    messages = await session_db.get_recent_messages(session_id, limit=3)
    assert len(messages) == 3
    # Should be oldest to newest
    assert messages[0].content == "Message 2"
    assert messages[1].content == "Message 3"
    assert messages[2].content == "Message 4"


@pytest.mark.asyncio
async def test_tool_call_logging(session_db):
    """Test logging tool calls."""
    session_id = await session_db.get_or_create_session(12345)

    await session_db.add_message(
        session_id,
        role="tool",
        content="Tool executed",
        tool_name="run_shell",
        tool_params={"command": "ls -la"},
        tool_result="file1\nfile2",
    )

    messages = await session_db.get_messages(session_id)
    assert len(messages) == 1
    assert messages[0].tool_name == "run_shell"
    assert messages[0].tool_params == {"command": "ls -la"}


@pytest.mark.asyncio
async def test_conversation_history(session_db):
    """Test getting conversation history for LLM context."""
    session_id = await session_db.get_or_create_session(12345)

    await session_db.add_message(session_id, "user", "Hello")
    await session_db.add_message(session_id, "assistant", "Hi there!")
    await session_db.add_message(session_id, "tool", "Result", tool_name="test_tool")

    history = await session_db.get_conversation_history(session_id)
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "tool"


@pytest.mark.asyncio
async def test_session_isolation(session_db):
    """Test that sessions are isolated by chat_id."""
    session1 = await session_db.get_or_create_session(111)
    session2 = await session_db.get_or_create_session(222)

    await session_db.add_message(session1, "user", "Message for chat 111")
    await session_db.add_message(session2, "user", "Message for chat 222")

    messages1 = await session_db.get_messages(session1)
    messages2 = await session_db.get_messages(session2)

    assert len(messages1) == 1
    assert len(messages2) == 1
    assert messages1[0].content == "Message for chat 111"
    assert messages2[0].content == "Message for chat 222"


@pytest.mark.asyncio
async def test_message_count_tracking(session_db):
    """Test that message_count is tracked in session metadata."""
    session_id = await session_db.get_or_create_session(12345)
    
    # Check initial count
    session = await session_db.get_session(session_id)
    assert session["message_count"] == 0
    
    # Add messages
    await session_db.add_message(session_id, "user", "Message 1")
    await session_db.add_message(session_id, "assistant", "Message 2")
    
    # Check updated count
    session = await session_db.get_session(session_id)
    assert session["message_count"] == 2


@pytest.mark.asyncio
async def test_clear_session(session_db):
    """Test clearing a session."""
    session_id = await session_db.get_or_create_session(12345)
    
    await session_db.add_message(session_id, "user", "Message 1")
    await session_db.add_message(session_id, "user", "Message 2")
    
    # Clear
    await session_db.clear_session(session_id)
    
    # Verify messages are gone
    messages = await session_db.get_messages(session_id)
    assert len(messages) == 0
    
    # Verify session still exists
    session = await session_db.get_session(session_id)
    assert session is not None
    assert session["message_count"] == 0


@pytest.mark.asyncio
async def test_model_message_history_storage(session_db):
    """Test get/set of pydantic-ai native message history (JSON)."""
    session_id = await session_db.get_or_create_session(12345)
    assert await session_db.get_model_message_history(session_id) is None
    await session_db.set_model_message_history(session_id, "[]")
    raw = await session_db.get_model_message_history(session_id)
    assert raw == "[]"
    await session_db.set_model_message_history(session_id, '[{"kind":"request"}]')
    raw = await session_db.get_model_message_history(session_id)
    assert "request" in raw


# ============ Memory Tests ============

@pytest.mark.asyncio
async def test_memory_save_and_retrieve(session_db):
    """Test saving and retrieving memory entries."""
    entry = MemoryEntry(
        key="test_project",
        category="Project",
        l0_abstract="Test project for unit tests",
        l1_overview="This is a test project to verify memory functionality works correctly.",
        l2_details="Full details about the test project including all configuration and setup.",
    )

    await session_db.save_memory(entry)

    retrieved = await session_db.get_memory("test_project")
    assert retrieved is not None
    assert retrieved.key == "test_project"
    assert retrieved.category == "Project"
    assert retrieved.l0_abstract == "Test project for unit tests"
    assert retrieved.access_count == 1  # Incremented on retrieval


@pytest.mark.asyncio
async def test_memory_search(session_db):
    """Test memory search functionality with FTS5."""
    # Add multiple memory entries
    entries = [
        MemoryEntry(key="api_config", category="Environment", l0_abstract="API configuration for services"),
        MemoryEntry(key="project_status", category="Project", l0_abstract="Current project status"),
        MemoryEntry(key="api_keys", category="Security", l0_abstract="API keys management"),
    ]

    for entry in entries:
        await session_db.save_memory(entry)

    # Search for "api"
    results = await session_db.search_memory("api")
    assert len(results) == 2

    # Search with category filter
    results = await session_db.search_memory("api", category="Security")
    assert len(results) == 1
    assert results[0].key == "api_keys"


@pytest.mark.asyncio
async def test_memory_l0_overview(session_db):
    """Test getting L0 overview."""
    entries = [
        MemoryEntry(key="s1", category="System", l0_abstract="System config 1"),
        MemoryEntry(key="s2", category="System", l0_abstract="System config 2"),
        MemoryEntry(key="p1", category="Project", l0_abstract="Project item 1"),
    ]

    for entry in entries:
        await session_db.save_memory(entry)

    overview = await session_db.get_l0_overview()
    assert "System" in overview
    assert "Project" in overview
    assert len(overview["System"]) == 2
    assert len(overview["Project"]) == 1


@pytest.mark.asyncio
async def test_memory_update(session_db):
    """Test updating existing memory entry."""
    entry = MemoryEntry(
        key="test_key",
        category="Project",
        l0_abstract="Original abstract",
    )
    await session_db.save_memory(entry)

    # Update the entry
    updated = MemoryEntry(
        key="test_key",
        category="Project",
        l0_abstract="Updated abstract",
        confidence=0.8,
    )
    await session_db.save_memory(updated)

    retrieved = await session_db.get_memory("test_key")
    assert retrieved.l0_abstract == "Updated abstract"
    assert retrieved.confidence == 0.8


@pytest.mark.asyncio
async def test_memory_access_count(session_db):
    """Test memory access count tracking."""
    entry = MemoryEntry(
        key="test_key",
        category="Project",
        l0_abstract="Test abstract",
    )
    await session_db.save_memory(entry)
    
    # Retrieve multiple times
    await session_db.get_memory("test_key")
    await session_db.get_memory("test_key")
    await session_db.get_memory("test_key")
    
    retrieved = await session_db.get_memory("test_key")
    assert retrieved.access_count == 4  # 3 retrievals + this one


@pytest.mark.asyncio
async def test_memory_delete(session_db):
    """Test deleting memory entry."""
    entry = MemoryEntry(
        key="test_key",
        category="Project",
        l0_abstract="Test abstract",
    )
    await session_db.save_memory(entry)
    
    # Verify it exists
    retrieved = await session_db.get_memory("test_key")
    assert retrieved is not None
    
    # Delete
    deleted = await session_db.delete_memory("test_key")
    assert deleted is True
    
    # Verify it's gone
    retrieved = await session_db.get_memory("test_key")
    assert retrieved is None


@pytest.mark.asyncio
async def test_memory_categories(session_db):
    """Test memory category validation."""
    # Test all valid categories
    for category in MEMORY_CATEGORIES:
        entry = MemoryEntry(
            key=f"test_{category}",
            category=category,
            l0_abstract=f"Test for {category}",
        )
        await session_db.save_memory(entry)
    
    # Verify all saved
    categories = await session_db.get_all_categories()
    for category in MEMORY_CATEGORIES:
        assert category in categories


# ============ SessionMessage Tests ============

def test_session_message_to_dict():
    """Test SessionMessage serialization."""
    msg = SessionMessage(
        role="user",
        content="Hello",
        timestamp=12345.0,
        tool_name="test_tool",
        tool_params={"key": "value"},
    )
    
    data = msg.to_dict()
    assert data["role"] == "user"
    assert data["content"] == "Hello"
    assert data["tool_name"] == "test_tool"
    assert data["tool_params"] == {"key": "value"}


def test_session_message_from_dict():
    """Test SessionMessage deserialization."""
    data = {
        "role": "assistant",
        "content": "Hi there",
        "timestamp": 12345.0,
    }
    
    msg = SessionMessage.from_dict(data)
    assert msg.role == "assistant"
    assert msg.content == "Hi there"


def test_session_message_to_model_message():
    """Test conversion to LLM-compatible format."""
    msg = SessionMessage(
        role="tool",
        content="Result",
        tool_name="test_tool",
        tool_result="success",
    )
    
    model_msg = msg.to_model_message()
    assert model_msg["role"] == "tool"
    assert model_msg["content"] == "Result"
    assert model_msg["tool_name"] == "test_tool"


# ============ MemoryEntry Tests ============

def test_memory_entry_to_dict():
    """Test MemoryEntry serialization."""
    entry = MemoryEntry(
        key="test",
        category="Project",
        l0_abstract="Abstract",
        l1_overview="Overview",
        l2_details="Details",
        confidence=0.9,
    )
    
    data = entry.to_dict()
    assert data["key"] == "test"
    assert data["category"] == "Project"
    assert data["l0_abstract"] == "Abstract"
    assert data["confidence"] == 0.9


def test_memory_entry_from_dict():
    """Test MemoryEntry deserialization."""
    data = {
        "key": "test",
        "category": "Project",
        "l0_abstract": "Abstract",
        "confidence": 0.8,
        "access_count": 5,
    }
    
    entry = MemoryEntry.from_dict(data)
    assert entry.key == "test"
    assert entry.category == "Project"
    assert entry.access_count == 5
