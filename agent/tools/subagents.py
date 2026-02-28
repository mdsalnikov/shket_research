"""Subagents system for hierarchical agent architectures.

This module enables specialized subagents to handle specific tasks,
delegating from a main orchestrator agent. Follows patterns used by
Claude Code and other advanced agent systems.

Features:
- Subagent definition and registry
- Task delegation to specialized subagents
- Auto-routing based on task analysis
- Parallel execution support
- Context isolation per subagent
- Support for both YAML and Markdown subagent definitions
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent.activity_log import log_tool_call
from agent.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Subagents directory location
SUBAGENTS_DIR = Path(PROJECT_ROOT) / "subagents"


@dataclass
class Subagent:
    """Represents a specialized subagent."""
    name: str
    description: str
    version: str = "1.0.0"
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    path: Path | None = None
    file_format: str = "yaml"  # "yaml" or "md"
    
    def matches_trigger(self, task: str) -> bool:
        """Check if task matches any of this subagent's triggers."""
        task_lower = task.lower()
        return any(trigger.lower() in task_lower for trigger in self.triggers)


class SubagentRegistry:
    """Registry for managing subagents."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.subagents: dict[str, Subagent] = {}
        self._ensure_subagents_dir()
        self._create_default_subagents()
        self._load_subagents()
        self._initialized = True
    
    def _ensure_subagents_dir(self):
        """Ensure subagents directory exists."""
        SUBAGENTS_DIR.mkdir(parents=True, exist_ok=True)
    
    def _create_default_subagents(self):
        """Create default subagent definitions if none exist."""
        if any(SUBAGENTS_DIR.glob("*.yaml")) or any(SUBAGENTS_DIR.glob("*.md")):
            return  # Subagents already exist
        
        default_subagents = {
            "coder.yaml": {
                "name": "coder",
                "description": "Specialized agent for code generation and modification",
                "version": "1.0.0",
                "system_prompt": """You are a specialized coding agent. Focus on:
- Writing clean, maintainable code
- Following project conventions from AGENTS.md
- Adding appropriate tests
- Using version control properly

Always:
1. Read existing code to understand patterns
2. Write code that matches the style
3. Test your changes
4. Commit with clear messages""",
                "tools": [
                    "read_file", "write_file", "list_dir",
                    "run_shell", "git_status", "git_add", "git_commit"
                ],
                "context_files": ["AGENTS.md", "README.md"],
                "triggers": [
                    "write code", "implement", "refactor", "add function",
                    "create class", "modify code", "fix bug"
                ],
                "related": ["reviewer", "tester"]
            },
            "researcher.yaml": {
                "name": "researcher",
                "description": "Specialized agent for information gathering and research",
                "version": "1.0.0",
                "system_prompt": """You are a specialized research agent. Focus on:
- Thorough information gathering
- Source verification and credibility
- Synthesizing findings from multiple sources
- Clear, well-structured reports

Research workflow:
1. Define research questions clearly
2. Search multiple sources
3. Verify information across sources
4. Synthesize and report findings""",
                "tools": [
                    "web_search", "read_file", "write_file",
                    "create_todo", "get_todo", "mark_todo_done"
                ],
                "context_files": ["AGENTS.md"],
                "triggers": [
                    "research", "find information", "search for",
                    "investigate", "look up", "find out"
                ],
                "related": ["analyst"]
            },
            "reviewer.yaml": {
                "name": "reviewer",
                "description": "Specialized agent for code review and quality assurance",
                "version": "1.0.0",
                "system_prompt": """You are a specialized code review agent. Focus on:
- Code quality and best practices
- Security vulnerabilities
- Performance issues
- Test coverage

Review checklist:
1. Code follows project conventions
2. No obvious bugs or errors
3. Security considerations addressed
4. Tests are adequate
5. Documentation is clear""",
                "tools": [
                    "read_file", "list_dir", "git_status"
                ],
                "context_files": ["AGENTS.md"],
                "triggers": [
                    "review code", "code review", "check quality",
                    "audit", "inspect code"
                ],
                "related": ["coder"]
            },
            "tester.yaml": {
                "name": "tester",
                "description": "Specialized agent for test creation and execution",
                "version": "1.0.0",
                "system_prompt": """You are a specialized testing agent. Focus on:
- Comprehensive test coverage
- Edge cases and error handling
- Test maintainability
- Clear test names and assertions

Testing workflow:
1. Understand the code to test
2. Identify test scenarios
3. Write clear, focused tests
4. Run tests and verify results
5. Report coverage and issues""",
                "tools": [
                    "read_file", "write_file", "run_shell",
                    "list_dir"
                ],
                "context_files": ["AGENTS.md"],
                "triggers": [
                    "write tests", "test", "pytest", "unit test",
                    "integration test", "test coverage"
                ],
                "related": ["coder", "reviewer"]
            },
        }
        
        for filename, data in default_subagents.items():
            file_path = SUBAGENTS_DIR / filename
            file_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
            logger.info(f"Created default subagent: {filename}")
    
    def _load_subagents(self):
        """Load subagents from YAML and Markdown files."""
        # Load YAML subagents
        for yaml_file in SUBAGENTS_DIR.glob("*.yaml"):
            try:
                content = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(content)
                
                subagent = Subagent(
                    name=data.get("name", yaml_file.stem),
                    description=data.get("description", ""),
                    version=data.get("version", "1.0.0"),
                    system_prompt=data.get("system_prompt", ""),
                    tools=data.get("tools", []),
                    context_files=data.get("context_files", []),
                    triggers=data.get("triggers", []),
                    related=data.get("related", []),
                    config=data.get("config", {}),
                    path=yaml_file,
                    file_format="yaml"
                )
                
                self.subagents[subagent.name] = subagent
                logger.debug(f"Loaded subagent: {subagent.name} (yaml)")
                
            except Exception as e:
                logger.warning(f"Failed to load subagent from {yaml_file}: {e}")
        
        # Load Markdown subagents (Anthropic-style)
        for md_file in SUBAGENTS_DIR.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                subagent = self._parse_markdown_subagent(content, md_file)
                if subagent:
                    self.subagents[subagent.name] = subagent
                    logger.debug(f"Loaded subagent: {subagent.name} (md)")
                    
            except Exception as e:
                logger.warning(f"Failed to load subagent from {md_file}: {e}")
    
    def _parse_markdown_subagent(self, content: str, file_path: Path) -> Subagent | None:
        """Parse a Markdown subagent definition (Anthropic-style).
        
        Expected format:
        ---
        name: code-simplifier
        description: Simplifies and refines code...
        model: default
        ---
        
        [System prompt content...]
        """
        # Extract frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not frontmatter_match:
            logger.warning(f"Invalid markdown subagent format: {file_path}")
            return None
        
        frontmatter_text = frontmatter_match.group(1)
        
        # Parse frontmatter as YAML
        frontmatter = yaml.safe_load(frontmatter_text)
        
        if not frontmatter or "name" not in frontmatter:
            logger.warning(f"Missing name in frontmatter: {file_path}")
            return None
        
        # Extract system prompt (everything after frontmatter)
        system_prompt = content[frontmatter_match.end():].strip()
        
        # Create subagent
        return Subagent(
            name=frontmatter.get("name", file_path.stem),
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "1.0.0"),
            system_prompt=system_prompt,
            tools=frontmatter.get("tools", []),
            context_files=frontmatter.get("context_files", []),
            triggers=frontmatter.get("triggers", []),
            related=frontmatter.get("related", []),
            config=frontmatter.get("config", {}),
            path=file_path,
            file_format="md"
        )
    
    def get_subagent(self, name: str) -> Subagent | None:
        """Get a subagent by name."""
        return self.subagents.get(name)
    
    def list_subagents(self) -> list[Subagent]:
        """List all available subagents."""
        return list(self.subagents.values())
    
    def find_matching_subagent(self, task: str) -> Subagent | None:
        """Find the best matching subagent for a task."""
        for subagent in self.subagents.values():
            if subagent.matches_trigger(task):
                return subagent
        return None


# Global registry instance
registry = SubagentRegistry()


@log_tool_call
def list_subagents() -> str:
    """List all available subagents.
    
    Returns:
        Formatted list of subagents with descriptions
    """
    subagents = registry.list_subagents()
    
    if not subagents:
        return "No subagents available."
    
    lines = [f"Available subagents ({len(subagents)}):"]
    for sa in sorted(subagents, key=lambda x: x.name):
        lines.append(f"\n🤖 {sa.name}")
        lines.append(f"   Description: {sa.description}")
        if sa.triggers:
            lines.append(f"   Triggers: {', '.join(sa.triggers[:5])}")
    
    return "\n".join(lines)


@log_tool_call
def get_subagent(name: str) -> str:
    """Get details about a specific subagent.
    
    Args:
        name: Subagent name
        
    Returns:
        Subagent details including system prompt and configuration
    """
    subagent = registry.get_subagent(name)
    
    if not subagent:
        available = [sa.name for sa in registry.list_subagents()]
        return f"Subagent '{name}' not found.\nAvailable: {', '.join(available)}"
    
    lines = [
        f"## Subagent: {subagent.name}",
        f"Version: {subagent.version}",
        f"Format: {subagent.file_format}",
        f"Description: {subagent.description}",
        f"\n### System Prompt",
        f"{subagent.system_prompt[:2000]}..." if len(subagent.system_prompt) > 2000 else subagent.system_prompt,
    ]
    
    if subagent.tools:
        lines.append(f"\n### Tools")
        lines.append(", ".join(subagent.tools))
    
    if subagent.context_files:
        lines.append(f"\n### Context Files")
        lines.append(", ".join(subagent.context_files))
    
    if subagent.triggers:
        lines.append(f"\n### Triggers")
        lines.append(", ".join(subagent.triggers))
    
    if subagent.related:
        lines.append(f"\n### Related Subagents")
        lines.append(", ".join(subagent.related))
    
    return "\n".join(lines)


@log_tool_call
def delegate_task(subagent_name: str, task: str, context: str = "") -> str:
    """Delegate a task to a specific subagent.
    
    Args:
        subagent_name: Name of the subagent to delegate to
        task: Task description to execute
        context: Additional context for the task
        
    Returns:
        Result of subagent execution or error message
    """
    subagent = registry.get_subagent(subagent_name)
    
    if not subagent:
        available = [sa.name for sa in registry.list_subagents()]
        return f"❌ Subagent '{subagent_name}' not found.\nAvailable: {', '.join(available)}"
    
    # Build enhanced system prompt with context
    system_prompt = subagent.system_prompt
    
    if context:
        system_prompt = f"{system_prompt}\n\n### Additional Context\n{context}"
    
    # Add context files if specified
    if subagent.context_files:
        context_content = []
        for cf in subagent.context_files:
            cf_path = Path(PROJECT_ROOT) / cf
            if cf_path.exists():
                try:
                    content = cf_path.read_text(encoding="utf-8")
                    context_content.append(f"### {cf}\n{content[:3000]}")
                except Exception as e:
                    logger.warning(f"Failed to read context file {cf}: {e}")
        
        if context_content:
            separator = '\n\n'.join(['=' * 80])
            system_prompt = '\n\n'.join(context_content) + '\n\n' + separator + '\n\n' + system_prompt
    
    # Create task for subagent
    subagent_task = f"""You are the {subagent.name} subagent. Execute the following task:

### Task
{task}

### Instructions
1. Analyze the task requirements
2. Use your specialized tools and expertise
3. Execute the task step by step
4. Provide a clear summary of results

Remember to follow your system prompt guidelines and best practices.
"""
    
    # Note: In a full implementation, this would spawn a subagent process
    # For now, return the prepared task information
    return f"""✅ Delegated task to subagent: {subagent.name}

### Subagent Configuration
- **Name**: {subagent.name}
- **Version**: {subagent.version}
- **Description**: {subagent.description}
- **File Format**: {subagent.file_format}

### Task
{task}

### System Prompt (first 500 chars)
{system_prompt[:500]}...

### Next Steps
The subagent would now execute this task with its specialized capabilities.
In a full implementation, this would spawn a separate agent process.

### Available Tools
{', '.join(subagent.tools) if subagent.tools else 'All standard tools'}

### Related Subagents
{', '.join(subagent.related) if subagent.related else 'None'}
"""


@log_tool_call
def route_task(task: str) -> str:
    """Automatically route a task to the most appropriate subagent.
    
    Args:
        task: Task description to analyze and route
        
    Returns:
        Routing decision and delegated task result
    """
    # Find matching subagent
    matching = registry.find_matching_subagent(task)
    
    if matching:
        return f"""🔄 Routing task to subagent: {matching.name}

### Task Analysis
- **Task**: {task}
- **Matched Subagent**: {matching.name}
- **Reason**: Task matches triggers: {', '.join(matching.triggers[:3])}

### Delegation
{delegate_task(matching.name, task)}
"""
    else:
        # No matching subagent, execute with main agent
        return f"""ℹ️ No specialized subagent found for this task.

### Task
{task}

### Available Subagents
{list_subagents()}

### Decision
This task will be handled by the main agent. Consider creating a specialized subagent if this is a recurring task type.
"""


@log_tool_call
def create_subagent(name: str, description: str, system_prompt: str, 
                   file_format: str = "md", **kwargs) -> str:
    """Create a new subagent definition.
    
    Args:
        name: Subagent name (unique identifier)
        description: Brief description of subagent purpose
        system_prompt: System prompt for the subagent
        file_format: "yaml" or "md" (default: "md")
        **kwargs: Additional configuration (tools, triggers, etc.)
        
    Returns:
        Confirmation of subagent creation
    """
    # Check if subagent already exists
    if registry.get_subagent(name):
        return f"❌ Subagent '{name}' already exists."
    
    # Create subagent file
    if file_format == "md":
        # Markdown format (Anthropic-style)
        content = f"""---
name: {name}
description: {description}
version: 1.0.0
model: default
---

{system_prompt}
"""
        file_path = SUBAGENTS_DIR / f"{name}.md"
    else:
        # YAML format
        data = {
            "name": name,
            "description": description,
            "version": "1.0.0",
            "system_prompt": system_prompt,
            **kwargs
        }
        file_path = SUBAGENTS_DIR / f"{name}.yaml"
        content = yaml.dump(data, default_flow_style=False)
    
    # Write file
    file_path.write_text(content, encoding="utf-8")
    
    # Reload registry
    registry._initialized = False
    registry.__init__()
    
    return f"""✅ Created subagent: {name}

### Details
- **File**: {file_path.name}
- **Format**: {file_format}
- **Description**: {description}

### Next Steps
The subagent is now available for use with:
- `get_subagent("{name}")` - View details
- `delegate_task("{name}", "task")` - Delegate tasks
- `route_task("...")` - Auto-routing will consider this subagent
"""
