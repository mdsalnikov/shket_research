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
"""

from __future__ import annotations

import logging
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
        if any(SUBAGENTS_DIR.glob("*.yaml")):
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
        """Load subagents from YAML files."""
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
                    path=yaml_file
                )
                
                self.subagents[subagent.name] = subagent
                logger.debug(f"Loaded subagent: {subagent.name}")
                
            except Exception as e:
                logger.warning(f"Failed to load subagent from {yaml_file}: {e}")
    
    def get_subagent(self, name: str) -> Subagent | None:
        """Get a subagent by name."""
        return self.subagents.get(name)
    
    def list_subagents(self) -> list[Subagent]:
        """List all registered subagents."""
        return list(self.subagents.values())
    
    def find_matching_subagent(self, task: str) -> Subagent | None:
        """Find the best matching subagent for a task."""
        task_lower = task.lower()
        
        # First, try exact trigger matches
        for subagent in self.subagents.values():
            if subagent.matches_trigger(task):
                return subagent
        
        # Then, try keyword matching in name, description, and triggers
        best_match = None
        best_score = 0
        
        # Keywords that should match specific subagents
        keyword_mapping = {
            "coder": ["code", "python", "function", "class", "write", "implement", "refactor", "script"],
            "researcher": ["research", "search", "find", "information", "investigate", "look up"],
            "reviewer": ["review", "check", "audit", "quality", "inspect"],
            "tester": ["test", "pytest", "unit", "coverage", "testing"],
        }
        
        for subagent in self.subagents.values():
            score = 0
            text_to_search = f"{subagent.name} {subagent.description} {' '.join(subagent.triggers)}".lower()
            
            # Check keyword mapping
            if subagent.name in keyword_mapping:
                for keyword in keyword_mapping[subagent.name]:
                    if keyword in task_lower:
                        score += 2  # Higher weight for mapped keywords
            
            # Count general keyword matches
            for word in task_lower.split():
                if len(word) > 3 and word in text_to_search:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = subagent
        
        return best_match if best_score > 0 else None


# Global registry instance
registry = SubagentRegistry()


async def list_subagents() -> str:
    """List all available subagents.
    
    Returns:
        Formatted list of subagents with descriptions.
    """
    with log_tool_call("list_subagents", "all") as tool_log:
        logger.info("Tool list_subagents: listing all subagents")
        
        try:
            subagents = registry.list_subagents()
            
            if not subagents:
                result = "No subagents available."
                tool_log.log_result("0 subagents")
                return result
            
            output_parts = ["# Available Subagents", ""]
            
            for subagent in subagents:
                output_parts.append(f"## {subagent.name}")
                output_parts.append(f"{subagent.description}")
                output_parts.append("")
                output_parts.append(f"**Version:** {subagent.version}")
                output_parts.append("")
                output_parts.append("**Tools:**")
                for tool in subagent.tools:
                    output_parts.append(f"- {tool}")
                output_parts.append("")
                output_parts.append("**Triggers:**")
                for trigger in subagent.triggers[:5]:  # Limit triggers shown
                    output_parts.append(f"- {trigger}")
                if len(subagent.triggers) > 5:
                    output_parts.append(f"- ... and {len(subagent.triggers) - 5} more")
                output_parts.append("")
            
            result = '\n'.join(output_parts)
            tool_log.log_result(f"{len(subagents)} subagents")
            return result
            
        except Exception as e:
            logger.error("list_subagents failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error listing subagents: {e}"


async def get_subagent(name: str) -> str:
    """Get detailed information about a specific subagent.
    
    Args:
        name: Name of the subagent
        
    Returns:
        Full subagent details.
    """
    with log_tool_call("get_subagent", name) as tool_log:
        logger.info("Tool get_subagent: loading %s", name)
        
        try:
            subagent = registry.get_subagent(name)
            
            if not subagent:
                # Try to find similar names
                similar = [
                    s.name for s in registry.list_subagents()
                    if name.lower() in s.name.lower()
                ]
                
                result = f"Subagent '{name}' not found."
                if similar:
                    result += f"\n\nSimilar subagents: {', '.join(similar)}"
                tool_log.log_result("not found")
                return result
            
            output_parts = [
                f"# {subagent.name}",
                "",
                subagent.description,
                "",
                f"**Version:** {subagent.version}",
                "",
                "## System Prompt",
                "",
                subagent.system_prompt or "(No custom system prompt)",
                "",
                "## Tools",
                "",
            ]
            
            for tool in subagent.tools:
                output_parts.append(f"- {tool}")
            
            output_parts.append("")
            output_parts.append("## Triggers")
            output_parts.append("")
            
            for trigger in subagent.triggers:
                output_parts.append(f"- {trigger}")
            
            if subagent.related:
                output_parts.append("")
                output_parts.append("## Related Subagents")
                output_parts.append("")
                for related in subagent.related:
                    output_parts.append(f"- {related}")
            
            result = '\n'.join(output_parts)
            tool_log.log_result("loaded")
            return result
            
        except Exception as e:
            logger.error("get_subagent failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error getting subagent: {e}"


async def delegate_task(subagent_name: str, task: str) -> str:
    """Delegate a task to a specific subagent.
    
    This simulates task delegation. In a full implementation, this would
    spawn a subagent with the appropriate context and tools.
    
    Args:
        subagent_name: Name of the subagent to delegate to
        task: Task to execute
        
    Returns:
        Result from the subagent.
    """
    with log_tool_call("delegate_task", f"{subagent_name}: {task[:50]}") as tool_log:
        logger.info("Tool delegate_task: delegating to %s", subagent_name)
        
        try:
            subagent = registry.get_subagent(subagent_name)
            
            if not subagent:
                result = f"Subagent '{subagent_name}' not found. Use list_subagents() to see available subagents."
                tool_log.log_result("subagent not found")
                return result
            
            # In a full implementation, this would:
            # 1. Create a subagent instance with the subagent's system prompt
            # 2. Load the subagent's tools
            # 3. Load context files
            # 4. Execute the task
            # 5. Return the result
            
            # For now, return a simulated response
            result = f"""# Task Delegated to {subagent_name}

**Subagent:** {subagent_name}
**Description:** {subagent.description}

## Task
{task}

## Available Tools
{', '.join(subagent.tools)}

## Status
In a full implementation, this subagent would now:
1. Load its system prompt and context
2. Execute the task using available tools
3. Return the result

For now, use the main agent with guidance from get_subagent('{subagent_name}')."""
            
            tool_log.log_result("delegated (simulated)")
            return result
            
        except Exception as e:
            logger.error("delegate_task failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error delegating task: {e}"


async def route_task(task: str) -> str:
    """Automatically route a task to the most appropriate subagent.
    
    Args:
        task: Task to route
        
    Returns:
        Routing decision and recommendation.
    """
    with log_tool_call("route_task", task[:50]) as tool_log:
        logger.info("Tool route_task: routing %s", task[:50])
        
        try:
            subagent = registry.find_matching_subagent(task)
            
            if not subagent:
                result = f"""# Task Routing

**Task:** {task}

**Decision:** No specific subagent matches this task.

**Recommendation:** Use the main agent to handle this task, or create a new subagent with appropriate triggers."""
                tool_log.log_result("no match")
                return result
            
            result = f"""# Task Routing

**Task:** {task}

**Matched Subagent:** {subagent.name}

**Description:** {subagent.description}

**Recommendation:** Delegate this task to the {subagent.name} subagent.

**To delegate:**
```
delegate_task('{subagent.name}', '{task}')
```

**Available Tools:** {', '.join(subagent.tools)}"""
            
            tool_log.log_result(f"routed to {subagent.name}")
            return result
            
        except Exception as e:
            logger.error("route_task failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error routing task: {e}"


async def create_subagent(name: str, description: str, tools: list[str], triggers: list[str], system_prompt: str = "") -> str:
    """Create a new subagent definition.
    
    Args:
        name: Subagent name
        description: Subagent description
        tools: List of tools for this subagent
        triggers: List of trigger phrases
        system_prompt: Custom system prompt
        
    Returns:
        Confirmation message.
    """
    with log_tool_call("create_subagent", name) as tool_log:
        logger.info("Tool create_subagent: creating %s", name)
        
        try:
            _ensure_subagents_dir()
            
            # Create subagent data
            data = {
                "name": name,
                "description": description,
                "version": "1.0.0",
                "system_prompt": system_prompt,
                "tools": tools,
                "context_files": ["AGENTS.md"],
                "triggers": triggers,
                "related": [],
                "config": {}
            }
            
            # Write YAML file
            file_path = SUBAGENTS_DIR / f"{name}.yaml"
            file_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
            
            # Reload registry
            registry._load_subagents()
            
            result = f"Subagent '{name}' created successfully."
            result += f"\n\nPath: {file_path}"
            result += f"\n\nUse `get_subagent('{name}')` to view details."
            tool_log.log_result("created")
            return result
            
        except Exception as e:
            logger.error("create_subagent failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error creating subagent: {e}"


def _ensure_subagents_dir():
    """Ensure subagents directory exists."""
    SUBAGENTS_DIR.mkdir(parents=True, exist_ok=True)
