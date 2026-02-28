"""AGENTS.md parser and reader tool.

This module provides functionality to read and parse AGENTS.md files
following the open standard for AI agent guidance.

Features:
- Parse AGENTS.md files from root and subdirectories
- Extract structured sections (overview, guidelines, rules, etc.)
- Provide context for agent operations
- Support multiple AGENTS.md files in project hierarchy
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


@dataclass
class AgentsMdSection:
    """A parsed section from AGENTS.md."""
    title: str
    content: str
    level: int  # Markdown heading level (1-6)
    subsections: list["AgentsMdSection"] = field(default_factory=list)


@dataclass
class AgentsMdDocument:
    """A parsed AGENTS.md document."""
    path: str
    title: str
    sections: list[AgentsMdSection] = field(default_factory=list)
    raw_content: str = ""
    
    # Extracted metadata
    project_name: str = ""
    project_description: str = ""
    rules: list[str] = field(default_factory=list)
    tools: list[dict[str, str]] = field(default_factory=list)
    env_vars: list[dict[str, str]] = field(default_factory=list)
    commands: list[dict[str, str]] = field(default_factory=list)


def _parse_markdown_headings(content: str) -> list[AgentsMdSection]:
    """Parse markdown headings and their content."""
    sections = []
    
    # Pattern to match headings and their content
    pattern = r'^(#{1,6})\s+(.+?)(?:\n|$)'
    
    lines = content.split('\n')
    current_section = None
    current_content = []
    
    for line in lines:
        match = re.match(pattern, line)
        if match:
            # Save previous section
            if current_section:
                current_section.content = '\n'.join(current_content).strip()
                current_section.subsections = _parse_markdown_headings('\n'.join(current_content))
                sections.append(current_section)
                current_content = []
            
            # Start new section
            level = len(match.group(1))
            title = match.group(2).strip()
            current_section = AgentsMdSection(
                title=title,
                content="",
                level=level
            )
        else:
            current_content.append(line)
    
    # Don't forget the last section
    if current_section:
        current_section.content = '\n'.join(current_content).strip()
        current_section.subsections = _parse_markdown_headings('\n'.join(current_content))
        sections.append(current_section)
    
    return sections


def _extract_rules(content: str) -> list[str]:
    """Extract numbered or bulleted rules from content."""
    rules = []
    
    # Match numbered lists like "1. Rule text"
    numbered_pattern = r'^\d+\.\s+(.+?)(?:\n|$)'
    # Match bullet points like "- Rule text" or "* Rule text"
    bullet_pattern = r'^[-*]\s+(.+?)(?:\n|$)'
    
    for line in content.split('\n'):
        line = line.strip()
        if re.match(numbered_pattern, line):
            rule = re.sub(numbered_pattern, r'\1', line).strip()
            if rule and len(rule) > 5:  # Avoid very short matches
                rules.append(rule)
        elif re.match(bullet_pattern, line):
            rule = re.sub(bullet_pattern, r'\1', line).strip()
            if rule and len(rule) > 5:
                rules.append(rule)
    
    return rules


def _extract_tools(content: str) -> list[dict[str, str]]:
    """Extract tool information from markdown tables or lists."""
    tools = []
    
    # Look for table patterns - more flexible pattern
    table_pattern = r'\|([^|]+)\|([^|]+)\|'
    for match in re.finditer(table_pattern, content, re.MULTILINE):
        tool_name = match.group(1).strip()
        purpose = match.group(2).strip()
        if tool_name and purpose and len(tool_name) > 1:
            tools.append({"name": tool_name, "purpose": purpose})
    
    return tools


def _extract_env_vars(content: str) -> list[dict[str, str]]:
    """Extract environment variable documentation."""
    env_vars = []
    
    # Look for table patterns with env vars - more flexible
    table_pattern = r'\|(`?([A-Z_]+)`?)\|([^|]+)\|'
    for match in re.finditer(table_pattern, content, re.MULTILINE):
        var_name = match.group(2).strip()
        description = match.group(3).strip()
        if var_name and description:
            env_vars.append({
                "name": var_name,
                "description": description,
                "required": "No"
            })
    
    return env_vars


def _extract_commands(content: str) -> list[dict[str, str]]:
    """Extract code blocks that look like commands."""
    commands = []
    
    # Look for bash code blocks
    bash_pattern = r'```bash\n([^`]+)```'
    for match in re.finditer(bash_pattern, content, re.MULTILINE | re.DOTALL):
        code = match.group(1).strip()
        # Extract the first line as the command
        first_line = code.split('\n')[0].strip()
        if first_line and not first_line.startswith('#'):
            commands.append({
                "command": first_line,
                "context": code
            })
    
    return commands


def parse_agents_md(content: str, path: str = "") -> AgentsMdDocument:
    """Parse AGENTS.md content into structured document.
    
    Args:
        content: Raw markdown content
        path: File path for reference
        
    Returns:
        Parsed AgentsMdDocument with sections and extracted metadata
    """
    # Extract title (first H1)
    title_match = re.search(r'^# (.+?)(?:\n|$)', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "AGENTS.md"
    
    # Parse sections
    sections = _parse_markdown_headings(content)
    
    # Extract metadata
    rules = _extract_rules(content)
    tools = _extract_tools(content)
    env_vars = _extract_env_vars(content)
    commands = _extract_commands(content)
    
    # Extract project description (first paragraph after title)
    # Simplified pattern to avoid regex errors
    project_description = ""
    if content.strip():
        lines = content.strip().split('\n')
        desc_lines = []
        started = False
        for line in lines:
            if line.startswith('#'):
                if started:
                    break  # Hit another heading
                if line.startswith('# '):
                    started = True  # Passed the title
                continue
            if started and line.strip():
                desc_lines.append(line.strip())
            elif started and not line.strip() and desc_lines:
                break  # Empty line after description
        
        project_description = ' '.join(desc_lines)[:200]
    
    return AgentsMdDocument(
        path=path,
        title=title,
        sections=sections,
        raw_content=content,
        project_name=title,
        project_description=project_description,
        rules=rules,
        tools=tools,
        env_vars=env_vars,
        commands=commands
    )


async def read_agents_md(path: str | None = None) -> str:
    """Read and parse AGENTS.md file.
    
    This tool reads AGENTS.md files from the project, following the
    open standard for AI agent guidance. It can read:
    - Root AGENTS.md (default)
    - Specific path if provided
    
    Args:
        path: Optional path to AGENTS.md file. If not provided, reads from project root.
        
    Returns:
        Formatted summary of the AGENTS.md content with key sections.
    """
    with log_tool_call("read_agents_md", path or "default (project root)") as tool_log:
        logger.info("Tool read_agents_md: reading %s", path or "project root AGENTS.md")
        
        try:
            # Determine file path
            if path:
                file_path = Path(path)
                if not file_path.is_absolute():
                    file_path = Path(PROJECT_ROOT) / file_path
            else:
                file_path = Path(PROJECT_ROOT) / "AGENTS.md"
            
            if not file_path.exists():
                result = f"AGENTS.md not found at: {file_path}"
                tool_log.log_result(result)
                return result
            
            # Read and parse
            content = file_path.read_text(encoding="utf-8")
            doc = parse_agents_md(content, str(file_path))
            
            # Build formatted output
            output_parts = [
                f"# {doc.title}",
                f"Source: {doc.path}",
                "",
            ]
            
            if doc.project_description:
                output_parts.append(f"**Description:** {doc.project_description}")
                output_parts.append("")
            
            # Add sections
            if doc.sections:
                output_parts.append("## Sections")
                for section in doc.sections:
                    if section.level <= 2:  # Only top-level sections
                        output_parts.append(f"### {section.title}")
                        # Add first few lines of content
                        lines = section.content.split('\n')[:3]
                        output_parts.append('\n'.join(lines))
                        output_parts.append("")
            
            # Add rules
            if doc.rules:
                output_parts.append("## Rules")
                for i, rule in enumerate(doc.rules[:10], 1):  # Limit to 10 rules
                    output_parts.append(f"{i}. {rule}")
                output_parts.append("")
            
            # Add tools
            if doc.tools:
                output_parts.append("## Tools")
                for tool in doc.tools:
                    output_parts.append(f"- **{tool.get('name', '')}**: {tool.get('purpose', '')}")
                output_parts.append("")
            
            # Add env vars
            if doc.env_vars:
                output_parts.append("## Environment Variables")
                for env in doc.env_vars:
                    req = f" (required)" if env.get('required', '').lower() in ('yes', 'true') else ""
                    output_parts.append(f"- `{env.get('name', '')}`{req}: {env.get('description', '')}")
                output_parts.append("")
            
            result = '\n'.join(output_parts)
            tool_log.log_result(f"parsed {len(doc.sections)} sections, {len(doc.rules)} rules")
            return result
            
        except Exception as e:
            logger.error("read_agents_md failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error reading AGENTS.md: {e}"


async def get_agents_rules() -> str:
    """Get rules from AGENTS.md.
    
    This tool extracts and returns the rules section from AGENTS.md
    for quick reference during task execution.
    
    Returns:
        List of rules from AGENTS.md.
    """
    with log_tool_call("get_agents_rules", "extract rules") as tool_log:
        logger.info("Tool get_agents_rules: extracting rules from AGENTS.md")
        
        try:
            file_path = Path(PROJECT_ROOT) / "AGENTS.md"
            
            if not file_path.exists():
                result = "AGENTS.md not found"
                tool_log.log_result(result)
                return result
            
            content = file_path.read_text(encoding="utf-8")
            doc = parse_agents_md(content, str(file_path))
            
            if not doc.rules:
                result = "No rules found in AGENTS.md"
                tool_log.log_result(result)
                return result
            
            output_parts = ["## Rules from AGENTS.md", ""]
            for i, rule in enumerate(doc.rules, 1):
                output_parts.append(f"{i}. {rule}")
            
            result = '\n'.join(output_parts)
            tool_log.log_result(f"{len(doc.rules)} rules")
            return result
            
        except Exception as e:
            logger.error("get_agents_rules failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error getting rules: {e}"


async def get_agents_context(topic: str | None = None) -> str:
    """Get relevant context from AGENTS.md for a specific topic.
    
    This tool searches AGENTS.md for sections relevant to the given topic
    and returns the most relevant information.
    
    Args:
        topic: Optional topic to search for (e.g., "testing", "tools", "deployment")
        
    Returns:
        Relevant sections from AGENTS.md.
    """
    with log_tool_call("get_agents_context", topic or "all") as tool_log:
        logger.info("Tool get_agents_context: searching for %s", topic or "all topics")
        
        try:
            file_path = Path(PROJECT_ROOT) / "AGENTS.md"
            
            if not file_path.exists():
                result = "AGENTS.md not found"
                tool_log.log_result(result)
                return result
            
            content = file_path.read_text(encoding="utf-8")
            doc = parse_agents_md(content, str(file_path))
            
            if not topic:
                # Return full summary
                return await read_agents_md()
            
            # Search for relevant sections
            topic_lower = topic.lower()
            relevant_sections = []
            
            for section in doc.sections:
                section_text = f"{section.title} {section.content}".lower()
                if topic_lower in section_text:
                    relevant_sections.append(section)
            
            if not relevant_sections:
                result = f"No relevant sections found for topic: {topic}"
                tool_log.log_result(result)
                return result
            
            output_parts = [f"## Context for: {topic}", ""]
            for section in relevant_sections:
                output_parts.append(f"### {section.title}")
                output_parts.append(section.content[:500])  # Limit section length
                if len(section.content) > 500:
                    output_parts.append("... [truncated]")
                output_parts.append("")
            
            result = '\n'.join(output_parts)
            tool_log.log_result(f"{len(relevant_sections)} sections")
            return result
            
        except Exception as e:
            logger.error("get_agents_context failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Error getting context: {e}"
