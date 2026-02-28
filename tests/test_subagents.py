"""Tests for SUBAGENTS system."""

import pytest
from pathlib import Path
import tempfile
import shutil
import yaml

from agent.tools.subagents import (
    Subagent,
    SubagentRegistry,
    registry,
    SUBAGENTS_DIR,
)


# ============ Subagent Tests ============

def test_subagent_dataclass():
    """Subagent dataclass works correctly."""
    subagent = Subagent(
        name="test",
        description="Test subagent",
        tools=["read_file", "write_file"],
        triggers=["test", "testing"]
    )
    
    assert subagent.name == "test"
    assert subagent.matches_trigger("run a test") is True
    assert subagent.matches_trigger("unrelated task") is False


def test_subagent_matches_trigger():
    """Subagent trigger matching works."""
    subagent = Subagent(
        name="coder",
        description="Code agent",
        triggers=["write code", "implement", "refactor"]
    )
    
    assert subagent.matches_trigger("write code for me") is True
    assert subagent.matches_trigger("implement this feature") is True
    assert subagent.matches_trigger("I need to refactor") is True
    assert subagent.matches_trigger("research something") is False


# ============ Registry Tests ============

def test_registry_singleton():
    """Registry is a singleton."""
    reg1 = SubagentRegistry()
    reg2 = SubagentRegistry()
    
    assert reg1 is reg2


def test_registry_creates_default_subagents():
    """Registry creates default subagents."""
    # Backup existing subagents
    backup_dir = None
    if SUBAGENTS_DIR.exists() and any(SUBAGENTS_DIR.glob("*.yaml")):
        backup_dir = Path(tempfile.mkdtemp())
        shutil.copytree(SUBAGENTS_DIR, backup_dir / "subagents", dirs_exist_ok=True)
        shutil.rmtree(SUBAGENTS_DIR)
    
    try:
        # Clear registry and recreate
        SubagentRegistry._instance = None
        reg = SubagentRegistry()
        
        # Check default subagents exist
        assert len(reg.subagents) > 0
        
        # Check specific subagents
        assert "coder" in reg.subagents or any("coder" in s.name for s in reg.list_subagents())
    finally:
        # Restore original subagents
        if backup_dir:
            shutil.rmtree(SUBAGENTS_DIR)
            shutil.move(backup_dir / "subagents", SUBAGENTS_DIR)
            shutil.rmtree(backup_dir)
        
        # Reset registry
        SubagentRegistry._instance = None


def test_registry_load_subagents():
    """Registry loads subagents from YAML files."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Create test subagent
        test_subagent = {
            "name": "test_agent",
            "description": "Test description",
            "tools": ["test_tool"],
            "triggers": ["test"]
        }
        
        yaml_file = temp_dir / "test_agent.yaml"
        yaml_file.write_text(yaml.dump(test_subagent), encoding="utf-8")
        
        # Temporarily replace SUBAGENTS_DIR
        from agent.tools import subagents
        original_dir = subagents.SUBAGENTS_DIR
        subagents.SUBAGENTS_DIR = temp_dir
        
        # Clear and reload registry
        SubagentRegistry._instance = None
        reg = SubagentRegistry()
        
        assert "test_agent" in reg.subagents
        
    finally:
        # Restore
        from agent.tools import subagents
        subagents.SUBAGENTS_DIR = original_dir
        SubagentRegistry._instance = None
        shutil.rmtree(temp_dir)


def test_registry_find_matching_subagent():
    """Registry finds matching subagent for task."""
    reg = SubagentRegistry()
    
    # Find coder for coding task
    coder = reg.find_matching_subagent("write a python function")
    assert coder is not None
    
    # Find researcher for research task
    researcher = reg.find_matching_subagent("research this topic")
    assert researcher is not None


# ============ Integration Tests ============

@pytest.mark.asyncio
async def test_list_subagents():
    """List subagents works correctly."""
    from agent.tools.subagents import list_subagents
    
    result = await list_subagents()
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "# Available Subagents" in result


@pytest.mark.asyncio
async def test_get_subagent():
    """Get specific subagent works."""
    from agent.tools.subagents import get_subagent
    
    # Get coder subagent
    result = await get_subagent("coder")
    
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_subagent_not_found():
    """Get non-existent subagent returns appropriate message."""
    from agent.tools.subagents import get_subagent
    
    result = await get_subagent("nonexistent_xyz")
    
    assert isinstance(result, str)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_delegate_task():
    """Delegate task to subagent."""
    from agent.tools.subagents import delegate_task
    
    result = await delegate_task("coder", "write a function")
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "coder" in result.lower()


@pytest.mark.asyncio
async def test_delegate_task_not_found():
    """Delegate to non-existent subagent."""
    from agent.tools.subagents import delegate_task
    
    result = await delegate_task("nonexistent", "do something")
    
    assert isinstance(result, str)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_route_task():
    """Route task to appropriate subagent."""
    from agent.tools.subagents import route_task
    
    result = await route_task("write a python script")
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "coder" in result.lower() or "subagent" in result.lower()


@pytest.mark.asyncio
async def test_route_task_research():
    """Route research task."""
    from agent.tools.subagents import route_task
    
    result = await route_task("research machine learning trends")
    
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_create_subagent():
    """Create a new subagent."""
    from agent.tools.subagents import create_subagent
    
    result = await create_subagent(
        name="test_created_agent",
        description="Test created agent",
        tools=["read_file"],
        triggers=["test_created"],
        system_prompt="You are a test agent."
    )
    
    assert isinstance(result, str)
    assert "created" in result.lower()
    
    # Verify file exists
    yaml_file = SUBAGENTS_DIR / "test_created_agent.yaml"
    assert yaml_file.exists()
    
    # Clean up
    yaml_file.unlink()


# ============ Edge Cases ============

def test_subagent_empty_triggers():
    """Subagent with no triggers doesn't match anything."""
    subagent = Subagent(
        name="no_triggers",
        description="No triggers",
        triggers=[]
    )
    
    assert subagent.matches_trigger("anything") is False


def test_subagent_case_insensitive():
    """Trigger matching is case insensitive."""
    subagent = Subagent(
        name="test",
        description="Test",
        triggers=["write code"]
    )
    
    assert subagent.matches_trigger("WRITE CODE") is True
    assert subagent.matches_trigger("Write Code") is True
    assert subagent.matches_trigger("write code") is True


# ============ Subagent Content Tests ============

@pytest.mark.asyncio
async def test_coder_subagent_content():
    """Coder subagent has expected content."""
    from agent.tools.subagents import get_subagent
    
    result = await get_subagent("coder")
    
    assert isinstance(result, str)
    assert "code" in result.lower()


@pytest.mark.asyncio
async def test_researcher_subagent_content():
    """Researcher subagent has expected content."""
    from agent.tools.subagents import get_subagent
    
    result = await get_subagent("researcher")
    
    assert isinstance(result, str)
    assert "research" in result.lower() or "information" in result.lower()
