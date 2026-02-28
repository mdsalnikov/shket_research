# Shket Research Agent

Autonomous LLM-powered research agent for executing tasks on an Ubuntu server. Supports CLI, Telegram bot, and deep research capabilities.

> **Version**: 0.4.5 | **License**: MIT | **Python**: 3.11+

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
│   ├── tester.yaml        # Test creation
│   └── code-simplifier.md # Code simplification (MANDATORY after self-mod)
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
- **Subagents**: Specialized agents for specific tasks (coder, researcher, code-simplifier)

### Design Patterns

1. **Dependency Injection**: All tools receive dependencies via `AgentDeps`
2. **Session Isolation**: Each chat has isolated session state
3. **Error Recovery**: Multi-layer healing with smart retries
4. **Tool Abstraction**: Consistent interface for all tools
5. **Subagent Delegation**: Route tasks to specialized agents

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

### Code Simplification Principles

After any code modification, the code-simplifier subagent ensures:

1. **Clarity over brevity**: Explicit code is better than clever one-liners
2. **No nested ternaries**: Use if/else chains for multiple conditions
3. **Meaningful names**: Variables and functions should explain their intent
4. **Single responsibility**: Functions should do one thing well
5. **Preserve functionality**: Never change what code does, only how it does it

---

## Tools

| Tool | Purpose |
|------|---------|
| `run_shell` | Execute shell commands (30s timeout) |
| `read_file` | Read file contents |
| `write_file` | Write content to file |
| `list_dir` | List directory contents |
| `web_search` | Search the web via DuckDuckGo |
| `browser_*` | Headless browser automation (8 tools) |
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
- **development**: Git, testing, and development workflows
- **research**: Information gathering and synthesis
- **devops**: Deployment, monitoring, and infrastructure

### Using Skills

```python
# Find relevant skills for a task
skills = find_relevant_skills("implement REST API")

# Get specific skill
skill = get_skill("python-rest-api")

# Create new skill
create_skill("custom-skill", "description", content)
```

---

## Subagents System

Subagents are specialized agents with isolated context for specific tasks.

### Available Subagents

| Subagent | Purpose | When to Use |
|----------|---------|-------------|
| `coder` | Code generation | Writing new code, refactoring |
| `researcher` | Information gathering | Deep research tasks |
| `reviewer` | Code review | Reviewing code changes |
| `tester` | Test creation | Writing unit/integration tests |
| `code-simplifier` | Code simplification | **MANDATORY after self-modification** |

### Code-Simplifier (MANDATORY)

After **any self-modification**, the code-simplifier subagent **MUST** be invoked:

```python
delegate_task("code-simplifier", "Review and simplify the recently modified code")
```

**What it does**:
- Analyzes recently modified code for clarity and maintainability
- Applies project standards from AGENTS.md
- Simplifies complex code while preserving functionality
- Runs tests to ensure nothing broke
- Provides a summary of improvements made

**Why it's mandatory**:
- Ensures consistent code quality
- Prevents code rot from quick fixes
- Maintains readability for future modifications
- Catches complexity before it becomes a problem

### Using Subagents

```python
# Auto-route to appropriate subagent
result = route_task("write a unit test for function X")

# Explicit delegation
result = delegate_task("coder", "implement feature Y")

# List available subagents
subagents = list_subagents()
```

---

## Self-Modification Protocol

When modifying your own code, follow this protocol:

### Phase 1: Prepare
1. `backup_codebase()` - Create full backup
2. Read current files with `read_file()`
3. Create branch for non-trivial changes

### Phase 2: Edit & Verify
4. Make changes with `write_file()`
5. Update VERSION file
6. Run `run_tests()` - all tests must pass
7. Run `run_agent_subprocess("run status")` - verify new code loads

### Phase 3: Commit & Push
- **Small fix**: Commit to main, push, request_restart
- **Large change**: Create PR, wait for user merge

### Phase 4: Code Simplification (MANDATORY)
8. **`delegate_task("code-simplifier", "Review and simplify the recently modified code")`**
   - This step ensures code quality after self-modification
   - Never skip this step

---

## Error Handling

### Self-Healing System

The agent has built-in error recovery:

- **CONTEXT_OVERFLOW**: Compress context and retry
- **NETWORK_ERROR**: Exponential backoff and retry
- **TIMEOUT**: Exponential backoff and retry
- **TOOL_ERROR**: Retry with adjusted parameters
- **UNRECOVERABLE**: Provide helpful fallback message

### Rollback

If self-modification fails:
```python
# List available backups
backups = list_backups()

# Restore from backup
restore_from_backup(".backup_20240101_120000")
```

---

## Progress Tracking

For multi-step tasks:

```python
# Create TODO list
create_todo(["step 1", "step 2", "step 3"])

# Check progress
todo = get_todo()

# Mark step complete
mark_todo_done(1)
```

Progress is visible to users in real-time, especially useful for:
- Long-running tasks
- Complex multi-step operations
- Telegram bot interactions

---

## Memory System

### Hierarchy

- **L0**: Quick abstract (one-line summary)
- **L1**: Category overview (2-3 sentences)
- **L2**: Full details (complete information)

### Categories

- **System**: Agent configuration and internals
- **Environment**: Runtime environment details
- **Skill**: Domain expertise and capabilities
- **Project**: Project-specific information
- **Comm**: Communication patterns and preferences
- **Security**: API keys and sensitive data

### Usage

```python
# Save to memory
remember(
    key="project_status",
    category="Project",
    abstract="Current development status",
    overview="Feature X completed, Y in progress",
    details="Full details here..."
)

# Recall from memory
info = recall("project status", category="Project")
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.4.5 | 2025-01-XX | Added code-simplifier subagent, mandatory after self-mod |
| 0.4.4 | 2025-01-XX | Browser tool integration (8 tools), progress tracking |
| 0.4.2 | 2025-01-XX | Self-healing enhancements, network/timeout handling |
| 0.4.0 | 2025-01-XX | Deep research system, skills, subagents |

---

## License

MIT License - see LICENSE file for details.
