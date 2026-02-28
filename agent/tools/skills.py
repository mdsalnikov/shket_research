"""Skills system for agent capabilities.

This module provides a structured way to define, discover, and use
specialized skills for the agent. Each skill represents domain expertise
or a task pattern that the agent can leverage.

Features:
- Skill discovery and listing
- Skill content retrieval
- Relevant skill suggestion based on task
- Context loading for agent operations
- Skill creation and management
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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
    related_skills: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.related_skills is None:
            self.related_skills = []
        if self.keywords is None:
            self.keywords = []
        if self.tools is None:
            self.tools = []


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
        
        # Extract keywords from "When to Use" section
        keywords = []
        in_when_to_use = False
        for line in lines:
            if "## When to Use" in line:
                in_when_to_use = True
                continue
            if in_when_to_use:
                if line.startswith('##'):
                    break
                if line.strip().startswith('-'):
                    # Extract keywords from the use case
                    use_case = line.strip()[1:].lower()
                    # Add important words as keywords
                    for word in use_case.split():
                        word = word.strip('.,;:!?')
                        if len(word) > 3 and word not in ['user', 'need', 'asks', 'about']:
                            keywords.append(word)
                    break  # Just take first use case
        
        # Extract tools from "Tools" section
        tools = []
        in_tools = False
        for line in lines:
            if "## Tools" in line:
                in_tools = True
                continue
            if in_tools:
                if line.startswith('##'):
                    break
                if line.strip().startswith('-'):
                    # Extract tool name (usually in backticks)
                    tool_match = re.search(r'`([^`]+)`', line)
                    if tool_match:
                        tools.append(tool_match.group(1))
        
        return Skill(
            name=name,
            category=category,
            description=description,
            path=path,
            content=content,
            related_skills=related,
            keywords=keywords[:20],  # Limit keywords
            tools=tools
        )
    except Exception as e:
        logger.warning(f"Failed to parse skill file {path}: {e}")
        return None


def _create_default_skills() -> None:
    """Create default skill files if skills directory is empty."""
    if SKILLS_DIR.exists() and any(SKILLS_DIR.glob("**/*.md")):
        return  # Skills already exist
    
    _ensure_skills_dir()
    
    # Create comprehensive default skills
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
        "programming/javascript.md": """# JavaScript Development

## Description
Expertise in JavaScript programming, including ES6+ features,
asynchronous programming, and modern frameworks.

## When to Use
- User asks about JavaScript code
- Need to write or debug JavaScript
- Node.js development questions
- Frontend framework questions

## Tools
- `run_shell`: Execute Node.js commands
- `read_file`: Read JavaScript source files
- `write_file`: Create or modify JavaScript files

## Patterns

### Modern JavaScript
Use ES6+ features:
```javascript
const array = [1, 2, 3];
const doubled = array.map(x => x * 2);
```

### Async/Await
Prefer async/await over callbacks:
```javascript
async function fetchData() {
    const response = await fetch(url);
    return await response.json();
}
```

## Related Skills
- programming
- testing
""",
        "devops/docker.md": """# Docker Containerization

## Description
Expertise in Docker containerization, including image creation,
container management, and Docker Compose.

## When to Use
- User asks about Docker
- Need to containerize applications
- Docker Compose configuration
- Container orchestration questions

## Tools
- `run_shell`: Execute Docker commands
- `read_file`: Read Dockerfiles and configs
- `write_file`: Create Docker configurations

## Patterns

### Multi-stage Builds
Reduce image size with multi-stage builds:
```dockerfile
FROM python:3.11 as builder
# Build steps

FROM python:3.11-slim
# Copy only necessary files
```

### Docker Compose
Define multi-container applications:
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
```

## Related Skills
- devops
- deployment
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
                output_parts.append(f"{skill.description}")
                if skill.tools:
                    output_parts.append(f"**Tools**: {', '.join(skill.tools[:5])}")
                if skill.related_skills:
                    output_parts.append(f"**Related**: {', '.join(skill.related_skills)}")
                output_parts.append("")
            
            result = "\n".join(output_parts)
            tool_log.log_result(f"{len(skills)} skills")
            return result
            
        except Exception as e:
            logger.error("list_skills failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error listing skills: {e}"


async def get_skill(skill_name: str) -> str:
    """Get a specific skill by name.
    
    This tool searches for a skill by name and returns its full content.
    The search is case-insensitive and supports partial matching.
    
    Args:
        skill_name: Name of the skill to retrieve
        
    Returns:
        Full skill content in markdown format.
    """
    with log_tool_call("get_skill", skill_name) as tool_log:
        logger.info("Tool get_skill: %s", skill_name)
        
        try:
            _ensure_skills_dir()
            _create_default_skills()
            
            # Normalize skill name for search
            normalized_name = skill_name.lower().replace(" ", "_").replace("-", "_")
            
            # Search for matching skill file
            skill_file = None
            for md_file in SKILLS_DIR.glob("**/*.md"):
                if md_file.stem.lower() == normalized_name:
                    skill_file = md_file
                    break
            
            # Try partial match if exact match fails
            if not skill_file:
                for md_file in SKILLS_DIR.glob("**/*.md"):
                    if normalized_name in md_file.stem.lower():
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
            
            # Extended keyword mapping
            skill_keywords = {
                "python": ["python", "pip", "virtualenv", "django", "flask", "pandas", "numpy"],
                "javascript": ["javascript", "js", "node", "npm", "react", "vue", "angular"],
                "git": ["git", "branch", "commit", "merge", "push", "pull", "repository", "clone"],
                "web_research": ["search", "research", "find", "look up", "investigate", "google"],
                "bash": ["bash", "shell", "script", "terminal", "command line", "linux"],
                "testing": ["test", "pytest", "unittest", "coverage", "assert"],
                "data_analysis": ["data", "analyze", "csv", "excel", "statistics", "pandas"],
                "docker": ["docker", "container", "dockerfile", "compose", "containerize"],
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
                
                # Check skill keywords
                keyword_matches = sum(1 for kw in skill.keywords if kw in task_lower)
                
                total_score = len(matches) + desc_matches + keyword_matches
                
                if total_score > 0:
                    relevant.append((skill, total_score))
            
            # Sort by relevance score
            relevant.sort(key=lambda x: x[1], reverse=True)
            
            if not relevant:
                result = "No specifically relevant skills found. You may want to explore available skills with list_skills()."
                tool_log.log_result("0 relevant")
                return result
            
            # Build output
            output_parts = ["# Relevant Skills", "", "Based on your task, these skills may be helpful:"]
            output_parts.append("")
            
            for skill, score in relevant[:5]:  # Top 5 skills
                output_parts.append(f"## {skill.name} (relevance: {score})")
                output_parts.append("")
                output_parts.append(skill.description)
                output_parts.append("")
                if skill.tools:
                    output_parts.append(f"**Useful tools**: {', '.join(skill.tools[:3])}")
                    output_parts.append("")
            
            result = "\n".join(output_parts)
            tool_log.log_result(f"{len(relevant)} relevant")
            return result
            
        except Exception as e:
            logger.error("find_relevant_skills failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error finding skills: {e}"


async def create_skill(name: str, category: str, content: str) -> str:
    """Create a new skill.
    
    This tool creates a new skill file in the skills directory.
    
    Args:
        name: Skill name (will be used as filename)
        category: Skill category (directory name)
        content: Full skill content in markdown format
        
    Returns:
        Confirmation message with skill path.
    """
    with log_tool_call("create_skill", f"{category}/{name}") as tool_log:
        logger.info("Tool create_skill: %s/%s", category, name)
        
        try:
            _ensure_skills_dir()
            
            # Create category directory if needed
            category_dir = SKILLS_DIR / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Create skill file
            skill_name = name.lower().replace(" ", "_").replace("-", "_")
            skill_path = category_dir / f"{skill_name}.md"
            
            # Write content
            skill_path.write_text(content, encoding="utf-8")
            
            result = f"Skill '{name}' created successfully.\n\n"
            result += f"Path: {skill_path}\n"
            result += f"Category: {category}\n"
            result += f"\nTo use this skill, reference it by name: '{skill_name}'"
            
            tool_log.log_result("created")
            return result
            
        except Exception as e:
            logger.error("create_skill failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error creating skill: {e}"


async def delete_skill(name: str) -> str:
    """Delete a skill.
    
    This tool deletes a skill file from the skills directory.
    
    Args:
        name: Skill name to delete
        
    Returns:
        Confirmation message.
    """
    with log_tool_call("delete_skill", name) as tool_log:
        logger.info("Tool delete_skill: %s", name)
        
        try:
            _ensure_skills_dir()
            
            # Normalize skill name
            normalized_name = name.lower().replace(" ", "_").replace("-", "_")
            
            # Find skill file
            skill_file = None
            for md_file in SKILLS_DIR.glob("**/*.md"):
                if md_file.stem.lower() == normalized_name:
                    skill_file = md_file
                    break
            
            if not skill_file:
                return f"Skill '{name}' not found."
            
            # Delete file
            skill_file.unlink()
            
            result = f"Skill '{name}' deleted successfully."
            
            tool_log.log_result("deleted")
            return result
            
        except Exception as e:
            logger.error("delete_skill failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error deleting skill: {e}"
