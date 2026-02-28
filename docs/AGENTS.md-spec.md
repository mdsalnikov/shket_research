# AGENTS.md Specification

## Overview

AGENTS.md is an open standard for guiding AI coding agents. Think of it as a README for agents — a dedicated, predictable place to provide context and instructions to help AI agents work effectively on your project.

**Key Facts:**
- Used by 60k+ open-source projects
- Formalized in August 2025 through collaboration between OpenAI, Google, Cursor, Factory, and Sourcegraph
- Donated to Linux Foundation on December 9, 2025
- Simple Markdown format — no new syntax to learn

## Purpose

AGENTS.md complements README.md by containing:
- Build steps and test commands
- Coding conventions and patterns
- Architecture documentation
- Environment setup instructions
- Tool usage guidelines
- Project-specific context

## Standard Sections

### 1. Project Overview
Brief description of the project to give the agent context.

```markdown
# Project Name

One or two sentences describing what the project does and its main purpose.
```

### 2. Quick Start / Getting Started
Essential commands to get the project running.

```markdown
## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -e .`
3. Run tests: `pytest tests/ -v`
```

### 3. Development Guidelines
Coding standards, patterns, and conventions.

```markdown
## Development Guidelines

- Use type hints for all function signatures
- Follow PEP 8 naming conventions
- Write docstrings for public APIs
- Tests must pass before committing
```

### 4. Architecture
High-level architecture overview and key components.

```markdown
## Architecture

```
┌─────────────────┐
│   CLI Interface │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Agent Core    │
└─────────────────┘
```

Key components:
- `agent/core/`: LLM orchestration
- `agent/tools/`: Tool implementations
- `agent/interfaces/`: CLI and Telegram bot
```

### 5. Tools and Dependencies
List of tools, their usage, and dependencies.

```markdown
## Tools

| Tool | Purpose |
|------|---------|
| `run_shell` | Execute OS commands |
| `web_search` | Search the web |
| `read_file` | Read file contents |

### Dependencies

- Python 3.11+
- pytest for testing
- ruff for linting
```

### 6. Testing
How to run tests and what test coverage is expected.

```markdown
## Testing

Run all tests:
```bash
pytest tests/ -v
```

Run specific test suite:
```bash
pytest tests/test_cli.py -v
```
```

### 7. Environment Setup
Environment variables and configuration.

```markdown
## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TG_BOT_KEY` | Telegram bot token | Yes (for bot) |
| `OPENROUTER_API_KEY` | OpenRouter API key | No (vLLM default) |
```

### 8. Common Tasks
Frequently performed tasks with step-by-step instructions.

```markdown
## Common Tasks

### Adding a new tool
1. Create file in `agent/tools/`
2. Register in `agent/tools/__init__.py`
3. Add to system prompt in `agent/core/agent.py`
4. Write tests in `tests/`
```

### 9. Rules and Constraints
Hard rules that must be followed.

```markdown
## Rules

1. Always create backups before self-modification
2. Run tests after any code change
3. Use branches for non-trivial changes
4. Never push without passing tests
```

## Best Practices

### Structure
- Use clear headings (##, ###)
- Use code blocks for commands
- Use tables for structured data
- Keep sections focused and scannable

### Content
- Be specific and actionable
- Include examples
- Document edge cases
- Update regularly

### Format
- Standard Markdown only
- No YAML frontmatter required
- No special syntax
- Human-readable

## File Locations

AGENTS.md can be placed at:
- Root of repository (most common)
- `docs/AGENTS.md` for larger projects
- Subdirectories for component-specific guidance

## Conflict Resolution

When multiple AGENTS.md files exist:
1. Root-level takes precedence for general guidance
2. Subdirectory files provide component-specific context
3. Agent should read all relevant files for complete context

## Examples

See the project's root `AGENTS.md` for a complete example.

## References

- [agents.md](https://agents.md/) - Official specification
- [GitHub Blog: How to write a great agents.md](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md/)
- [OpenAI Codex: Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
