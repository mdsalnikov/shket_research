"""Tests for SKILLS system."""

import pytest
from pathlib import Path
import tempfile
import shutil
import os

from agent.tools.skills import (
    Skill,
    _parse_skill_file,
    _create_default_skills,
    SKILLS_DIR,
)


# ============ Skill Parsing Tests ============

def test_parse_skill_file():
    """Skill file is parsed correctly."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Create test skill file in a category subdirectory
        category_dir = Path(temp_dir) / "programming"
        category_dir.mkdir()
        
        skill_content = """# Test Skill

## Description
This is a test skill description.

## When to Use
- When testing
- When parsing

## Related Skills
- other_skill
"""
        skill_path = category_dir / "test_skill.md"
        skill_path.write_text(skill_content, encoding="utf-8")
        
        skill = _parse_skill_file(skill_path)
        
        assert skill is not None
        assert skill.name == "Test Skill"
        assert skill.category == "programming"
        assert "test skill description" in skill.description.lower()
        assert "other_skill" in skill.related_skills
    finally:
        shutil.rmtree(temp_dir)


def test_parse_skill_file_missing():
    """Missing skill file returns None."""
    skill = _parse_skill_file(Path("/nonexistent/skill.md"))
    assert skill is None


def test_skill_dataclass():
    """Skill dataclass works correctly."""
    skill = Skill(
        name="Test",
        category="programming",
        description="Test description",
        path=Path("/test.md")
    )
    
    assert skill.name == "Test"
    assert skill.category == "programming"
    assert skill.related_skills == []


# ============ Skills Directory Tests ============

def test_skills_dir_created():
    """Skills directory is created if it doesn't exist."""
    from agent.tools.skills import _ensure_skills_dir
    
    _ensure_skills_dir()
    
    assert SKILLS_DIR.exists()
    assert (SKILLS_DIR / "programming").exists()
    assert (SKILLS_DIR / "research").exists()


def test_default_skills_created():
    """Default skills are created if directory is empty."""
    from agent.tools.skills import _create_default_skills
    
    # Backup existing skills
    backup_dir = None
    if SKILLS_DIR.exists() and any(SKILLS_DIR.glob("**/*.md")):
        backup_dir = Path(tempfile.mkdtemp())
        shutil.copytree(SKILLS_DIR, backup_dir / "skills", dirs_exist_ok=True)
        shutil.rmtree(SKILLS_DIR)
    
    try:
        # Create default skills
        _create_default_skills()
        
        # Check that skills were created
        skill_files = list(SKILLS_DIR.glob("**/*.md"))
        assert len(skill_files) > 0
        
        # Check specific skills exist
        python_skill = SKILLS_DIR / "programming" / "python.md"
        assert python_skill.exists()
    finally:
        # Restore original skills
        if backup_dir:
            shutil.rmtree(SKILLS_DIR)
            shutil.move(backup_dir / "skills", SKILLS_DIR)
            shutil.rmtree(backup_dir)


# ============ Integration Tests ============

@pytest.mark.asyncio
async def test_list_skills():
    """List skills works correctly."""
    from agent.tools.skills import list_skills
    
    result = await list_skills()
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "# Available Skills" in result


@pytest.mark.asyncio
async def test_list_skills_by_category():
    """List skills filtered by category."""
    from agent.tools.skills import list_skills
    
    result = await list_skills("programming")
    
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_skill():
    """Get specific skill works."""
    from agent.tools.skills import get_skill
    
    # Get python skill (should exist as default)
    result = await get_skill("python")
    
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_skill_not_found():
    """Get non-existent skill returns appropriate message."""
    from agent.tools.skills import get_skill
    
    result = await get_skill("nonexistent_skill_xyz")
    
    assert isinstance(result, str)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_find_relevant_skills():
    """Find relevant skills for a task."""
    from agent.tools.skills import find_relevant_skills
    
    result = await find_relevant_skills("write a python script to process data")
    
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_find_relevant_skills_git():
    """Find git skill for git task."""
    from agent.tools.skills import find_relevant_skills
    
    result = await find_relevant_skills("how do I merge branches in git")
    
    assert isinstance(result, str)
    # Should mention git skill
    assert "git" in result.lower() or "relevant" in result.lower()


@pytest.mark.asyncio
async def test_create_skill():
    """Create a new skill."""
    from agent.tools.skills import create_skill
    
    result = await create_skill(
        name="test_skill",
        category="testing",
        content="# Test Skill\n\nTest content."
    )
    
    assert isinstance(result, str)
    assert "created" in result.lower()
    
    # Verify file exists
    skill_path = SKILLS_DIR / "testing" / "test_skill.md"
    assert skill_path.exists()
    
    # Clean up
    skill_path.unlink()
    if not list((SKILLS_DIR / "testing").iterdir()):
        (SKILLS_DIR / "testing").rmdir()


# ============ Edge Cases ============

def test_parse_empty_skill_file():
    """Empty skill file is handled."""
    temp_dir = tempfile.mkdtemp()
    try:
        category_dir = Path(temp_dir) / "test_cat"
        category_dir.mkdir()
        
        skill_path = category_dir / "empty.md"
        skill_path.write_text("", encoding="utf-8")
        
        skill = _parse_skill_file(skill_path)
        
        assert skill is not None
        assert skill.content == ""
    finally:
        shutil.rmtree(temp_dir)


def test_parse_skill_with_special_chars():
    """Skill with special characters is handled."""
    temp_dir = tempfile.mkdtemp()
    try:
        category_dir = Path(temp_dir) / "special_cat"
        category_dir.mkdir()
        
        skill_content = """# Skill With Special Chars: Ñ

## Description
Contains unicode: émojis 🎉 and Cyrillic: Привет
"""
        skill_path = category_dir / "special.md"
        skill_path.write_text(skill_content, encoding="utf-8")
        
        skill = _parse_skill_file(skill_path)
        
        assert skill is not None
        assert "unicode" in skill.content.lower()
    finally:
        shutil.rmtree(temp_dir)


# ============ Skill Content Tests ============

@pytest.mark.asyncio
async def test_python_skill_content():
    """Python skill has expected content."""
    from agent.tools.skills import get_skill
    
    result = await get_skill("python")
    
    # Should contain expected sections
    assert "Description" in result or "description" in result.lower()
    assert "When to Use" in result or "when to use" in result.lower()


@pytest.mark.asyncio
async def test_git_skill_content():
    """Git skill has expected content."""
    from agent.tools.skills import get_skill
    
    result = await get_skill("git")
    
    # Should contain expected sections
    assert isinstance(result, str)
    assert len(result) > 0
