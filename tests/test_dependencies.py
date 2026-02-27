"""Tests for dependencies module with OpenClaw-inspired session management."""

import pytest
import tempfile
import os

from agent.session_db import SessionDB
from agent.session import MEMORY_CATEGORIES


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
async def session_db(temp_db_path):
    """Create and initialize a SessionDB instance."""
    db = SessionDB(temp_db_path)
    await db.init()
    yield db
    await db.close()


# ============ AgentDeps Creation Tests ============

@pytest.mark.asyncio
async def test_agent_deps_creation(session_db):
    """Test creating AgentDeps."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    assert deps.chat_id == 12345
    assert deps.session_id == session_id
    assert deps.session_scope == "main"


@pytest.mark.asyncio
async def test_agent_deps_with_scope(session_db):
    """Test AgentDeps with different scopes."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345, scope="per-peer")
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345, session_scope="per-peer")

    assert deps.session_scope == "per-peer"


# ============ Message Operations Tests ============

@pytest.mark.asyncio
async def test_agent_deps_message_operations(session_db):
    """Test message operations through AgentDeps."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.add_user_message("Hello!")
    await deps.add_assistant_message("Hi!")

    messages = await deps.get_history(limit=10)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_agent_deps_conversation_history(session_db):
    """Test getting conversation history in LLM format."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.add_user_message("Question?")
    await deps.add_assistant_message("Answer!")

    history = await deps.get_conversation_history(limit=10)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_agent_deps_tool_call_logging(session_db):
    """Test logging tool calls through AgentDeps."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.add_tool_call(
        tool_name="run_shell",
        params={"command": "ls"},
        result="file1\nfile2",
    )

    messages = await deps.get_history()
    assert len(messages) == 1
    assert messages[0].tool_name == "run_shell"


# ============ Memory Operations Tests ============

@pytest.mark.asyncio
async def test_agent_deps_memory_operations(session_db):
    """Test memory operations through AgentDeps."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.save_memory("test", "Project", "Test abstract")
    entry = await deps.recall_memory("test")
    assert entry is not None
    assert entry.l0_abstract == "Test abstract"


@pytest.mark.asyncio
async def test_agent_deps_memory_full_hierarchy(session_db):
    """Test saving memory with full L0/L1/L2 hierarchy."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.save_memory(
        key="full_test",
        category="Project",
        l0_abstract="Quick summary",
        l1_overview="Two or three sentence overview of the project.",
        l2_details="Full detailed information about the project including all specifics.",
        confidence=0.95,
    )
    
    entry = await deps.recall_memory("full_test")
    assert entry is not None
    assert entry.l0_abstract == "Quick summary"
    assert entry.l1_overview == "Two or three sentence overview of the project."
    assert entry.l2_details == "Full detailed information about the project including all specifics."
    assert entry.confidence == 0.95


@pytest.mark.asyncio
async def test_agent_deps_memory_search(session_db):
    """Test memory search through AgentDeps."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.save_memory("api_config", "Environment", "API configuration")
    await deps.save_memory("api_keys", "Security", "API keys storage")

    results = await deps.search_memory("api")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_agent_deps_memory_search_with_category(session_db):
    """Test memory search with category filter."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.save_memory("api_config", "Environment", "API configuration")
    await deps.save_memory("api_keys", "Security", "API keys storage")

    results = await deps.search_memory("api", category="Security")
    assert len(results) == 1
    assert results[0].key == "api_keys"


@pytest.mark.asyncio
async def test_agent_deps_memory_delete(session_db):
    """Test deleting memory through AgentDeps."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    await deps.save_memory("test_delete", "Project", "Test")
    
    deleted = await deps.delete_memory("test_delete")
    assert deleted is True
    
    entry = await deps.recall_memory("test_delete")
    assert entry is None


@pytest.mark.asyncio
async def test_agent_deps_context_summary(session_db):
    """Test getting L0 context summary."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    # Empty memory should return empty string
    summary = await deps.get_context_summary()
    assert summary == ""

    # Add some memories
    await deps.save_memory("s1", "System", "System config")
    await deps.save_memory("p1", "Project", "Project status")
    
    summary = await deps.get_context_summary()
    assert "System" in summary
    assert "Project" in summary
    assert "System config" in summary


# ============ Category Validation Tests ============

@pytest.mark.asyncio
async def test_agent_deps_memory_category_validation(session_db):
    """Test that invalid categories are handled."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    # Invalid category should be replaced with 'Project'
    await deps.save_memory("test", "InvalidCategory", "Test abstract")
    
    entry = await deps.recall_memory("test")
    assert entry.category == "Project"


@pytest.mark.asyncio
async def test_agent_deps_all_memory_categories(session_db):
    """Test all valid memory categories."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    for category in MEMORY_CATEGORIES:
        await deps.save_memory(f"test_{category}", category, f"Test for {category}")
    
    for category in MEMORY_CATEGORIES:
        entry = await deps.recall_memory(f"test_{category}")
        assert entry is not None
        assert entry.category == category


# ============ Runtime State Tests ============

@pytest.mark.asyncio
async def test_agent_deps_runtime_state(session_db):
    """Test runtime state tracking."""
    from agent.dependencies import AgentDeps

    session_id = await session_db.get_or_create_session(12345)
    deps = AgentDeps(db=session_db, session_id=session_id, chat_id=12345)

    # Initial state
    assert deps.retry_count == 0
    assert deps.last_error is None
    assert deps.current_task is None

    # Update state
    deps.retry_count = 2
    deps.last_error = "Test error"
    deps.current_task = "Test task"

    assert deps.retry_count == 2
    assert deps.last_error == "Test error"
    assert deps.current_task == "Test task"
