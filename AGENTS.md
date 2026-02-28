# Shket Research Agent

Autonomous LLM-powered research agent for executing tasks on an Ubuntu server. Supports CLI, Telegram bot, and deep research capabilities.

> **Version**: 0.4.2 | **License**: MIT | **Python**: 3.11+

---

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run a task
python -m agent run "your task here"

# Run with specific provider
python -m agent run "your task" --provider openrouter

# Start Telegram bot
python -m agent bot
```

---

## Project Structure

```
shket_research/
├── agent/                  # Main agent package
│   ├── __init__.py        # Package initialization
│   ├── __main__.py        # CLI entry point
│   ├── config.py          # Configuration management
│   ├── session.py         # Session management (SQLite)
│   ├── session_db.py      # Database operations
│   ├── dependencies.py    # Dependency injection
│   ├── activity_log.py    # Activity logging
│   ├── core/              # Core agent components
│   ├── healing/           # Self-healing system
│   │   ├── classifier.py  # Error classification
│   │   ├── compressor.py  # Context compression
│   │   ├── fallback.py    # Fallback responses
│   │   └── strategies.py  # Healing strategies
│   ├── interfaces/        # External interfaces
│   └── tools/             # Agent tools
│       ├── shell.py       # Shell execution
│       ├── filesystem.py  # File operations
│       ├── web.py         # Web search
│       ├── deep_research.py
│       ├── git.py         # Git operations
│       ├── gh.py          # GitHub CLI
│       ├── memory.py      # Memory operations
│       ├── skills.py      # Skills system
│       ├── subagents.py   # Subagent system
│       └── todo.py        # TODO management
├── skills/                # Domain expertise skills
│   ├── programming/       # Programming skills
│   ├── development/       # Development skills
│   ├── research/          # Research skills
│   └── devops/            # DevOps skills
├── subagents/             # Specialized subagents
│   ├── coder.yaml         # Code generation
│   ├── researcher.yaml    # Information gathering
│   ├── reviewer.yaml      # Code review
│   └── tester.yaml        # Test creation
├── tests/                 # Test suite
│   ├── test_cli.py        # CLI tests
│   ├── test_healing.py    # Self-healing tests
│   ├── test_deep_research.py
│   ├── test_skills.py     # Skills tests
│   ├── test_subagents.py  # Subagent tests
│   └── ...
├── data/                  # Data directory
│   └── sessions.db        # SQLite session database
├── logs/                  # Log files
├── scripts/               # Utility scripts
├── AGENTS.md             # This file
├── README.md             # User documentation
├── pyproject.toml        # Project configuration
└── VERSION               # Version file
```

---

## Architecture

### Core Components

- **Core**: Pydantic AI with dependency injection
- **Sessions**: SQLite-based persistence (OpenClaw-inspired)
- **Memory**: L0/L1/L2 hierarchy for efficient retrieval
- **Tools**: Shell, filesystem, web search, git, GitHub CLI, deep research
- **Self-Healing**: Error classification, context compression, fallback generation

### Design Patterns

1. **Dependency Injection**: All tools receive dependencies via `AgentDeps`
2. **Session Isolation**: Each chat has isolated session state
3. **Error Recovery**: Multi-layer healing with smart retries
4. **Tool Abstraction**: Consistent interface for all tools

---

## Code Style and Conventions

### Python Style

- **Formatter**: `ruff format`
- **Linter**: `ruff check`
- **Type Hints**: Required for all new code
- **Docstrings**: Google style for public APIs

### Naming Conventions

- **Files**: snake_case (e.g., `deep_research.py`)
- **Classes**: PascalCase (e.g., `DeepResearchAgent`)
- **Functions/Variables**: snake_case (e.g., `execute_step`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_RETRIES`)

### Documentation

```python
def example_function(param: str) -> int:
    """Brief one-line description.
    
    Extended description if needed.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
        
    Example:
        result = example_function("test")
    """
    return 42
```

---

## Tools

| Tool | Purpose |
|------|---------|
| `run_shell` | Execute shell commands (30s timeout) |
| `read_file` | Read file contents |
| `write_file` | Write content to file |
| `list_dir` | List directory contents |
| `web_search` | Search the web via DuckDuckGo |
| `deep_research` | Multi-step autonomous research |
| `quick_research` | Single-step research query |
| `compare_sources` | Compare info across sources |
| `create_todo` | Create task plan |
| `get_todo` | Get current task plan |
| `mark_todo_done` | Mark task step complete |
| `backup_codebase` | Create full backup |
| `list_backups` | List available backups |
| `restore_from_backup` | Restore from backup |
| `run_tests` | Run pytest in subprocess |
| `run_agent_subprocess` | Run agent in fresh subprocess |
| `git_*` | Git version control operations |
| `run_gh` | GitHub CLI operations |
| `recall` | Recall from memory |
| `remember` | Save to memory |
| `read_agents_md` | Read AGENTS.md context |
| `list_skills` | List available skills |
| `get_skill` | Get specific skill |
| `find_relevant_skills` | Find skills for task |
| `list_subagents` | List available subagents |
| `delegate_task` | Delegate to subagent |
| `route_task` | Auto-route to subagent |

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TG_BOT_KEY` | Telegram bot API key | Bot only | - |
| `OPENROUTER_API_KEY` | OpenRouter API key | Cloud mode | - |
| `VLLM_BASE_URL` | vLLM API endpoint | Local mode | http://localhost:8000/v1 |
| `VLLM_MODEL_NAME` | vLLM model identifier | Local mode | Qwen/Qwen3.5-27B |
| `OPENROUTER_MODEL_NAME` | OpenRouter model | Cloud mode | openai/gpt-oss-120b |
| `PROVIDER_DEFAULT` | Default provider | No | vllm |
| `AGENT_MODEL` | Override model | No | - |
| `AGENT_MAX_RETRIES` | Max retry attempts | No | 10 |
| `TG_WHITELIST` | Allowed TG usernames | No | (all) |

---

## Commands

### Development

```bash
# Run unit tests
pytest tests/test_cli.py -v

# Run full test suite
pytest tests/ -v

# Run agent capability tests (requires vLLM or OpenRouter)
USE_VLLM=1 pytest tests/test_agent_capabilities.py -v

# Lint code
ruff check .

# Format code
ruff format .
```

### Agent Operations

```bash
# Run a simple task
python -m agent run "list files in current directory"

# Run with OpenRouter
python -m agent run "research topic" --provider openrouter

# Check agent status
python -m agent run "run status"

# Start Telegram bot
python -m agent bot
```

---

## Testing Guidelines

### Test Organization

- **Unit Tests**: `tests/test_*.py` - Test individual components
- **Integration Tests**: `tests/test_integration_*.py` - Test component interactions
- **Agent Tests**: `tests/test_agent_*.py` - Test agent capabilities

### Writing Tests

```python
import pytest
from agent.healing.classifier import ErrorClassifier, ErrorType

def test_classifier_context_overflow():
    """Context overflow errors are classified correctly."""
    classifier = ErrorClassifier()
    error = ValueError("context too long")
    classified = classifier.classify(error)
    
    assert classified.error_type == ErrorType.CONTEXT_OVERFLOW
    assert classified.is_retryable is True
```

### Running Tests

```bash
# Specific test file
pytest tests/test_healing.py -v

# Specific test function
pytest tests/test_healing.py::test_classifier_context_overflow -v

# With coverage
pytest tests/ --cov=agent --cov-report=html
```

---

## Skills System

Skills provide domain expertise and task patterns. Located in `skills/` directory.

### Available Categories

- **programming**: Python, JavaScript, and other programming skills
- **development**: Git, code review, and development workflows
- **research**: Web research, data analysis, and literature review
- **devops**: Deployment, CI/CD, and infrastructure

### Using Skills

```python
# List all skills
await list_skills()

# Get skills by category
await list_skills("programming")

# Get specific skill
await get_skill("python")

# Find relevant skills for a task
await find_relevant_skills("write a python script")

# Create a new skill
await create_skill(
    name="my_skill",
    category="custom",
    content="# My Skill\n\nSkill content..."
)
```

### Skill Format

```markdown
# Skill Name

## Description
Brief description of what this skill covers.

## When to Use
- Use case 1
- Use case 2
- Use case 3

## Tools
- Tool 1: Description
- Tool 2: Description

## Patterns
Common patterns and best practices.

## Related Skills
- related_skill_1
- related_skill_2
```

---

## Subagents System

Subagents are specialized agents that handle specific types of tasks.

### Available Subagents

- **coder**: Code generation and modification
- **researcher**: Information gathering and research
- **reviewer**: Code review and quality assurance
- **tester**: Test creation and execution

### Using Subagents

```python
# List all subagents
await list_subagents()

# Get specific subagent
await get_subagent("coder")

# Delegate task to subagent
await delegate_task("coder", "write a function")

# Auto-route task to appropriate subagent
await route_task("write a python script")

# Create a new subagent
await create_subagent(
    name="my_agent",
    description="Custom agent",
    tools=["read_file", "write_file"],
    triggers=["custom", "trigger"],
    system_prompt="You are a custom agent..."
)
```

### Subagent Format (YAML)

```yaml
name: agent_name
description: Brief description
version: 1.0.0
system_prompt: |
  You are a specialized agent. Focus on...
tools:
  - tool1
  - tool2
context_files:
  - AGENTS.md
  - README.md
triggers:
  - trigger1
  - trigger2
related:
  - related_agent
```

---

## Deep Research System

Advanced multi-step research capabilities.

### Tools

- **deep_research**: Full multi-step research with synthesis
- **quick_research**: Single-step quick lookup
- **compare_sources**: Compare information across sources

### Using Deep Research

```python
# Full deep research
await deep_research(
    "machine learning in healthcare",
    goals=["find advances", "identify challenges"],
    max_steps=10,
    max_depth=3
)

# Quick research
await quick_research("python best practices")

# Compare sources
await compare_sources("React vs Vue")
```

### Research Workflow

1. **Plan**: Create research plan based on topic and goals
2. **Search**: Execute multi-step searches with refinement
3. **Verify**: Cross-reference findings across sources
4. **Synthesize**: Group findings by theme
5. **Report**: Generate structured report with confidence scores

---

## Self-Healing System

The agent can recover from errors and continue operation.

### Error Types

- **Context Overflow**: Compress history and continue
- **Usage Limit**: Generate fallback response
- **Rate Limit**: Wait and retry
- **Auth Error**: Abort with clear message
- **Recoverable**: Retry with exponential backoff

### Healing Strategies

1. **Classifier**: Categorize error type
2. **Compressor**: Reduce context size if needed
3. **Fallback**: Generate helpful response for non-recoverable errors
4. **Strategies**: Determine action based on error type

---

## Memory System

Long-term memory with L0/L1/L2 hierarchy.

### Memory Levels

- **L0 (Abstract)**: One-line summary
- **L1 (Overview)**: 2-3 sentence overview
- **L2 (Details)**: Full detailed information

### Using Memory

```python
# Save to memory
await remember(
    key="project_status",
    category="Project",
    abstract="Project is in development",
    overview="Active development with regular updates",
    details="Full details about the project..."
)

# Recall from memory
await recall(query="project status")
await recall(query="API config", category="System")
```

### Categories

- **System**: System configuration and settings
- **Environment**: Environment-specific information
- **Skill**: Skills and capabilities
- **Project**: Project-specific information
- **Comm**: Communication preferences
- **Security**: Security-related information

---

## Session Management

SQLite-based session persistence with per-chat isolation.

### Features

- Isolated session state per chat
- SQLite database for persistence
- OpenClaw-inspired architecture
- Automatic session cleanup

---

## Git and GitHub Integration

Full version control support with GitHub CLI.

### Git Operations

```bash
git_status    # Check repository status
git_add       # Stage files
git_commit    # Create commit
git_push      # Push to remote
git_pull      # Pull from remote
git_checkout  # Switch branches
```

### GitHub CLI

```python
# Create PR
await run_gh("pr create --title '...' --body '...'")

# View PR
await run_gh("pr view")

# List PRs
await run_gh("pr list")
```

---

## Self-Modification Protocol

When modifying agent code, follow this protocol:

### Phase 1 — Prepare

1. **backup_codebase()** — Create full backup
2. **Read current files** — Understand code to change
3. **Branch** — Create branch for non-trivial changes

### Phase 2 — Edit & Verify

4. **Make changes** — Use write_file for modifications
5. **Update VERSION** — Bump version number
6. **run_tests()** — Run test suite
7. **run_agent_subprocess()** — Test in fresh subprocess

### Phase 3 — Deploy

**Small Fix**: Commit to main, push, restart

**Large Change**: Create PR, do not merge yourself

### Rollback

Use `restore_from_backup(backup_dir)` if anything fails.

---

## Best Practices

### For Agents

1. Always read AGENTS.md at the start of complex tasks
2. Use `find_relevant_skills` to discover domain expertise
3. Use `route_task` to delegate to specialized subagents
4. Use `create_todo` for multi-step tasks
5. Always test code changes before committing

### For Developers

1. Write tests for all new features
2. Follow the self-modification protocol
3. Keep commits small and atomic
4. Use meaningful commit messages
5. Update documentation when changing behavior

---

## Troubleshooting

### Common Issues

**Agent not responding**: Check provider configuration and API keys

**Tests failing**: Run `pytest tests/test_cli.py -v` to isolate issue

**Self-modification failed**: Use `restore_from_backup` to rollback

**Subagent not routing correctly**: Check trigger patterns in YAML

**Skills not loading**: Ensure skills are in correct directory structure

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and write tests
4. Run full test suite
5. Create a pull request
6. Wait for review and merge

---

## License

MIT License - see LICENSE file for details.
