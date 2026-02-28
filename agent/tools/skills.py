"""Skills system for agent capabilities.

This module provides a structured way to define, discover, and use
specialized skills for the agent. Each skill represents domain expertise
or a task pattern that the agent can leverage.

Features:
- Skill discovery and listing
- Skill content retrieval
- Relevant skill suggestion based on task
- Context loading for agent operations
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Skills directory location
SKILLS_DIR = Path(PROJECT_ROOT) / "skills"


@dataclass
class Skill:
    """Represents a skill in the system."""
    name: str
    category: str
    description: str
    path: Path
    content: str = ""
    related_skills: list[str] = None
    
    def __post_init__(self):
        if self.related_skills is None:
            self.related_skills = []


def _ensure_skills_dir() -> None:
    """Ensure skills directory exists."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create default categories
    for category in ["programming", "research", "development", "devops"]:
        (SKILLS_DIR / category).mkdir(exist_ok=True)


def _parse_skill_file(path: Path) -> Skill | None:
    """Parse a skill markdown file into a Skill object."""
    try:
        content = path.read_text(encoding="utf-8")
        
        # Extract skill name from first heading
        name = path.stem.replace("_", " ").title()
        
        # Determine category from directory
        category = path.parent.name
        
        # Extract description (first paragraph after title)
        lines = content.split('\n')
        description_lines = []
        started = False
        for line in lines:
            if line.startswith('# '):
                if started:
                    break
                started = True
                continue
            if started and line.strip():
                description_lines.append(line.strip())
            elif started and not line.strip() and description_lines:
                break
        
        description = ' '.join(description_lines)[:200] if description_lines else ""
        
        # Extract related skills
        related = []
        in_related = False
        for line in lines:
            if "## Related Skills" in line:
                in_related = True
                continue
            if in_related:
                if line.startswith('##'):
                    break
                if line.strip().startswith('-'):
                    skill = line.strip()[1:].strip()
                    if skill:
                        related.append(skill)
        
        return Skill(
            name=name,
            category=category,
            description=description,
            path=path,
            content=content,
            related_skills=related
        )
    except Exception as e:
        logger.warning(f"Failed to parse skill file {path}: {e}")
        return None


def _create_default_skills() -> None:
    """Create default skill files if skills directory is empty."""
    if SKILLS_DIR.exists() and any(SKILLS_DIR.glob("**/*.md")):
        return  # Skills already exist
    
    _ensure_skills_dir()
    
    # Create some default skills
    default_skills = {
        "programming/python.md": """# Python Development

## Description
Expertise in Python programming, including modern Python 3.x features, 
best practices, debugging, and testing.

## When to Use
- User asks about Python code
- Need to write or debug Python scripts
- Python package management questions
- Async Python programming

## Tools
- `run_shell`: Execute Python scripts and commands
- `read_file`: Read Python source files
- `write_file`: Create or modify Python files
- `run_tests`: Run pytest test suites

## Patterns

### Virtual Environment Setup
Always use virtual environments for Python projects:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Testing Pattern
Write tests before or alongside code:
```python
def test_function():
    assert function(input) == expected
```

## Related Skills
- data_analysis
- testing
- bash
""",
        "development/git.md": """# Git Version Control

## Description
Expertise in Git version control, including branching strategies, 
merge conflicts, and collaborative workflows.

## When to Use
- User asks about Git operations
- Need to manage version control
- Branching and merging tasks
- Git history analysis

## Tools
- `git_status`: Check repository status
- `git_add`: Stage files
- `git_commit`: Create commits
- `git_push`: Push to remote
- `git_pull`: Pull from remote
- `git_checkout`: Switch branches

## Patterns

### Feature Branch Workflow
1. Create feature branch: `git checkout -b feature/name`
2. Make changes and commit
3. Push branch: `git push -u origin feature/name`
4. Create pull request
5. After merge: `git checkout main && git pull`

### Commit Message Convention
- Use present tense: "Add feature" not "Added feature"
- Keep subject line under 50 characters
- Reference issues: "Fix #123"

## Related Skills
- development
- code_review
""",
        "research/web_research.md": """# Web Research

## Description
Multi-step web research capabilities, including search, 
synthesis, and source verification.

## When to Use
- User asks research questions
- Need to find information online
- Multi-source verification needed
- Current information required

## Tools
- `web_search`: Search the web using DuckDuckGo
- `read_file`: Read saved research notes
- `write_file`: Save research findings

## Patterns

### Research Workflow
1. Define research question clearly
2. Perform initial broad search
3. Refine based on initial results
4. Verify across multiple sources
5. Synthesize findings

### Source Evaluation
- Check publication date
- Verify author credibility
- Cross-reference with other sources
- Note any biases

## Related Skills
- data_analysis
- literature_review
""",
    }
    
    for rel_path, content in default_skills.items():
        file_path = SKILLS_DIR / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Created default skill: {rel_path}")


async def list_skills(category: str | None = None) -> str:
    """List available skills, optionally filtered by category.
    
    This tool discovers all available skills in the skills directory
    and returns a formatted list.
    
    Args:
        category: Optional category filter (e.g., "programming", "research")
        
    Returns:
        Formatted list of skills with descriptions.
    """
    with log_tool_call("list_skills", category or "all") as tool_log:
        logger.info("Tool list_skills: listing skills (category: %s)", category or "all")
        
        try:
            _ensure_skills_dir()
            _create_default_skills()
            
            skills = []
            
            # Scan skills directory
            for md_file in SKILLS_DIR.glob("**/*.md"):
                skill = _parse_skill_file(md_file)
                if skill:
                    # Filter by category if specified
                    if category is None or skill.category == category:
                        skills.append(skill)
            
            if not skills:
                result = "No skills found."
                if category:
                    result += f" (category: {category})"
                tool_log.log_result("0 skills")
                return result
            
            # Sort by category, then name
            skills.sort(key=lambda s: (s.category, s.name))
            
            # Build output
            output_parts = ["# Available Skills", ""]
            
            current_category = None
            for skill in skills:
                if skill.category != current_category:
                    current_category = skill.category
                    output_parts.append(f"## {current_category.title()}")
                    output_parts.append("")
                
                output_parts.append(f"### {skill.name}")
                if skill.description:
                    output_parts.append(f"{skill.description}")
                output_parts.append("")
            
            result = '\n'.join(output_parts)
            tool_log.log_result(f"{len(skills)} skills")
            return result
            
        except Exception as e:
            logger.error("list_skills failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error listing skills: {e}"


async def get_skill(skill_name: str) -> str:
    """Get detailed information about a specific skill.
    
    This tool loads and returns the full content of a skill file.
    
    Args:
        skill_name: Name of the skill (e.g., "python", "git")
        
    Returns:
        Full skill content.
    """
    with log_tool_call("get_skill", skill_name) as tool_log:
        logger.info("Tool get_skill: loading %s", skill_name)
        
        try:
            _ensure_skills_dir()
            _create_default_skills()
            
            # Normalize skill name
            normalized_name = skill_name.lower().replace(" ", "_")
            
            # Search for the skill file
            skill_file = None
            for md_file in SKILLS_DIR.glob("**/*.md"):
                if md_file.stem == normalized_name or md_file.stem.replace("_", " ").lower() == normalized_name:
                    skill_file = md_file
                    break
            
            if not skill_file:
                # Try to find similar skills
                similar = []
                for md_file in SKILLS_DIR.glob("**/*.md"):
                    if normalized_name in md_file.stem.lower():
                        similar.append(md_file.stem)
                
                result = f"Skill '{skill_name}' not found."
                if similar:
                    result += f"\n\nSimilar skills: {', '.join(similar)}"
                tool_log.log_result("not found")
                return result
            
            # Load and return skill
            skill = _parse_skill_file(skill_file)
            if not skill:
                return f"Failed to parse skill: {skill_name}"
            
            tool_log.log_result("loaded")
            return skill.content
            
        except Exception as e:
            logger.error("get_skill failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error getting skill: {e}"


async def find_relevant_skills(task: str) -> str:
    """Find skills relevant to a given task.
    
    This tool analyzes the task description and suggests relevant skills
    based on keyword matching and skill metadata.
    
    Args:
        task: Task description to analyze
        
    Returns:
        List of relevant skills with explanations.
    """
    with log_tool_call("find_relevant_skills", task[:50]) as tool_log:
        logger.info("Tool find_relevant_skills: analyzing task %s", task[:50])
        
        try:
            _ensure_skills_dir()
            _create_default_skills()
            
            # Keywords to match against skills
            task_lower = task.lower()
            
            skill_keywords = {
                "python": ["python", "pip", "virtualenv", "django", "flask", "pandas"],
                "git": ["git", "branch", "commit", "merge", "push", "pull", "repository"],
                "web_research": ["search", "research", "find", "look up", "investigate"],
                "bash": ["bash", "shell", "script", "terminal", "command line"],
                "testing": ["test", "pytest", "unittest", "coverage"],
                "data_analysis": ["data", "analyze", "csv", "excel", "statistics"],
            }
            
            relevant = []
            
            # Scan all skills
            for md_file in SKILLS_DIR.glob("**/*.md"):
                skill = _parse_skill_file(md_file)
                if not skill:
                    continue
                
                # Check if skill has matching keywords
                skill_name_lower = skill.name.lower()
                skill_desc_lower = skill.description.lower()
                
                # Check keyword matches
                matches = []
                for skill_key, keywords in skill_keywords.items():
                    if skill_key in skill_name_lower:
                        for keyword in keywords:
                            if keyword in task_lower:
                                matches.append(keyword)
                                break
                
                # Check if task words appear in skill description
                task_words = task_lower.split()
                desc_matches = sum(1 for word in task_words if word in skill_desc_lower and len(word) > 3)
                
                if matches or desc_matches > 2:
                    relevant.append((skill, len(matches) + desc_matches))
            
            # Sort by relevance score
            relevant.sort(key=lambda x: x[1], reverse=True)
            
            if not relevant:
                result = "No specifically relevant skills found. You may want to explore available skills with list_skills()."
                tool_log.log_result("0 relevant")
                return result
            
            # Build output
            output_parts = ["# Relevant Skills", "", "Based on your task, these skills may be helpful:"]
            output_parts.append("")
            
            for skill, score in relevant[:5]:  # Top 5
                output_parts.append(f"## {skill.name} (relevance: {score})")
                output_parts.append(f"{skill.description}")
                output_parts.append("")
                output_parts.append(f"Use `get_skill('{skill.name}')` to load full details.")
                output_parts.append("")
            
            result = '\n'.join(output_parts)
            tool_log.log_result(f"{len(relevant)} relevant")
            return result
            
        except Exception as e:
            logger.error("find_relevant_skills failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error finding relevant skills: {e}"


async def create_skill(name: str, category: str, content: str) -> str:
    """Create a new skill file.
    
    This tool creates a new skill in the skills directory.
    
    Args:
        name: Skill name (e.g., "my_skill")
        category: Skill category (e.g., "programming", "research")
        content: Full markdown content for the skill
        
    Returns:
        Confirmation message.
    """
    with log_tool_call("create_skill", f"{category}/{name}") as tool_log:
        logger.info("Tool create_skill: creating %s/%s", category, name)
        
        try:
            _ensure_skills_dir()
            
            # Create category directory
            category_dir = SKILLS_DIR / category
            category_dir.mkdir(exist_ok=True)
            
            # Write skill file
            skill_file = category_dir / f"{name}.md"
            skill_file.write_text(content, encoding="utf-8")
            
            result = f"Skill '{name}' created successfully in category '{category}'."
            result += f"\n\nPath: {skill_file}"
            tool_log.log_result("created")
            return result
            
        except Exception as e:
            logger.error("create_skill failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error creating skill: {e}"
