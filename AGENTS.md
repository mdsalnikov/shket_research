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
- **development**: Git, code review, testing
- **research**: Web research, literature review
- **devops**: Deployment, CI/CD, infrastructure

### Using Skills

```python
# Find relevant skills for a task
find_relevant_skills("write a python script")

# Get specific skill
get_skill("python")

# List all skills
list_skills()

# List skills by category
list_skills("programming")
```

---

## Subagents

Subagents are specialized agents for specific tasks. Located in `subagents/` directory.

### Available Subagents

| Subagent | Purpose |
|----------|---------|
| `coder` | Code generation and modification |
| `researcher` | Information gathering and research |
| `reviewer` | Code review and quality assurance |
| `tester` | Test creation and execution |

### Using Subagents

```python
# List subagents
list_subagents()

# Get subagent details
get_subagent("coder")

# Delegate task to specific subagent
delegate_task("coder", "write a function")

# Auto-route task to appropriate subagent
route_task("research this topic")
```

---

## Deep Research

Advanced multi-step research capabilities.

### Features

- **Multi-step planning**: Automatic research plan generation
- **Iterative refinement**: Follow-up searches based on findings
- **Source verification**: Cross-reference information
- **Synthesis**: Combine findings into coherent reports

### Usage

```python
# Full deep research
deep_research(
    "machine learning trends 2024",
    goals=["find latest developments", "identify key players"],
    max_steps=10,
    max_depth=3
)

# Quick research
quick_research("python async await")

# Compare sources
compare_sources("react vs vue")
```

---

## Self-Healing

The agent includes robust error recovery:

1. **Error Classification**: Distinguishes recoverable vs fatal errors
2. **Context Compression**: Reduces context for overflow errors
3. **Fallback Generation**: Creates meaningful responses from partial results
4. **Smart Retries**: Non-retryable errors don't waste attempts

### Error Types

- **RECOVERABLE**: Can retry with adjusted approach
- **CONTEXT_OVERFLOW**: Need to compress context before retry
- **RATE_LIMIT**: Wait and retry (backoff)
- **NETWORK_ERROR**: Retry with exponential backoff
- **TIMEOUT**: Retry with exponential backoff
- **USAGE_LIMIT**: Account/quota limit - cannot retry
- **AUTH_ERROR**: Authentication error - cannot retry
- **FATAL**: Cannot recover, need fallback response

---

## Memory

L0/L1/L2 memory hierarchy:

- **L0**: Quick abstract (one-line summary)
- **L1**: Category overview (2-3 sentences)
- **L2**: Full details (complete information)

Categories: System, Environment, Skill, Project, Comm, Security

---

## Self-Modification Protocol

When modifying yourself, follow this protocol:

### PHASE 1 — PREPARE

1. `backup_codebase()` — Create full backup
2. Read current files with `read_file`
3. Create branch for non-trivial changes

### PHASE 2 — EDIT & VERIFY

4. Make changes with `write_file`
5. Update VERSION file
6. Run `run_tests()`
7. Run `run_agent_subprocess("run status")`

### PHASE 3A — SMALL FIX

- Commit to main: `git_add(["."])`, `git_commit()`, `git_push()`

### PHASE 3B — LARGER CHANGE

- Create PR: `run_gh("pr create --title '...' --body '...'")`
- Do NOT merge yourself
- Wait for user review

---

## Rules

1. Always use tools when the task requires OS, file, or web interaction
2. Prefer simple shell one-liners; avoid interactive commands
3. Write scripts to files, then execute with `run_shell`
4. For research: use `web_search` for simple, `deep_research` for complex
5. Be concise and precise in final answers
6. Always test scripts after writing them
7. Use `create_todo` for multi-step tasks
8. Never skip `backup_codebase()` before self-modification
9. Never push before tests pass
10. Never merge PRs yourself unless explicitly asked

---

## Security Considerations

### API Keys

- Never commit API keys to the repository
- Use `.env` file for local development
- Use environment variables in production

### Shell Commands

- Shell commands are executed with 30s timeout
- No sudo/root privileges
- Sanitize user input before shell execution

### File Operations

- File operations limited to project directory
- No execution of arbitrary files
- Backup before self-modification

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and run tests
4. Create a pull request
5. Wait for review

---

## License

MIT License
