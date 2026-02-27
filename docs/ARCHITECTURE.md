# Shket Research Agent Architecture

## Overview

Shket Research Agent follows the OpenClaw-inspired architecture with SQLite session persistence and Pydantic AI framework integration.

## Key Concepts

### Session Management (OpenClaw-inspired)

Sessions are the core isolation unit:

```
┌─────────────────────────────────────────┐
│            Session Key Format           │
│     agent:<agentId>:<scope>:<chatId>    │
└─────────────────────────────────────────┘
```

- **agent:shket:main:12345** — Main session for chat 12345
- **agent:shket:per-peer:12345** — Per-peer isolated session

**Session Scopes (dmScope from OpenClaw):**
- `main` — All DMs share the main session for continuity
- `per-peer` — Isolate by sender ID across channels
- `per-channel-peer` — Isolate by channel+peer combination

### Memory Hierarchy (L0/L1/L2)

Memory uses a three-level hierarchy for efficient retrieval:

| Level | Name | Purpose | Size |
|-------|------|---------|------|
| L0 | Abstract | One-line summary | ~1 line |
| L1 | Overview | 2-3 sentence context | ~2-3 lines |
| L2 | Details | Full content | Unlimited |

**Memory Categories:**
- System — System configuration and state
- Environment — Environment variables and paths
- Skill — Learned skills and patterns
- Project — Project-specific information
- Comm — Communication preferences
- Security — Security-related memories

## Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                   Control Interfaces                 │
│              CLI            Telegram Bot             │
└─────────────────────┬───────────────┬────────────────┘
                      │               │
                      ▼               ▼
              ┌─────────────────────────────┐
              │        Agent Core           │
              │   (Pydantic AI + Runner)    │
              └──────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌────────────────┐   ┌──────────────┐
│  SessionDB    │   │  Tool Executor │   │ LLM Backend  │
│  (SQLite)     │   │  (21 tools)    │   │ (OpenRouter) │
└───────┬───────┘   └────────────────┘   └──────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│              Database Schema              │
├───────────────────────────────────────────┤
│ sessions                                  │
│  - session_key (unique)                   │
│  - chat_id, agent_id, scope               │
│  - message_count, metadata                │
├───────────────────────────────────────────┤
│ messages                                  │
│  - session_id → sessions.id               │
│  - role, content, timestamp               │
│  - tool_name, tool_params, tool_result    │
├───────────────────────────────────────────┤
│ memory                                    │
│  - key (unique), category                 │
│  - l0_abstract, l1_overview, l2_details   │
│  - confidence, access_count               │
├───────────────────────────────────────────┤
│ memory_fts (FTS5)                         │
│  - Full-text search for memory            │
└───────────────────────────────────────────┘
```

## Components

### 1. SessionDB (`agent/session_db.py`)

SQLite-based session storage with:
- Persistent sessions with chat isolation
- Conversation history with configurable limits
- Tool call logging with parameters and results
- FTS5 full-text search for memory

### 2. AgentDeps (`agent/dependencies.py`)

Dependency injection container for Pydantic AI:
- Database reference (SessionDB)
- Session ID and chat context
- Message and memory operations
- Runtime state tracking

### 3. Agent Core (`agent/core/agent.py`)

Pydantic AI agent builder:
- `build_session_agent()` — Full session support
- `build_agent()` — Legacy mode without sessions
- Dynamic system prompt with memory context
- Tool registration (21 tools)

### 4. Runner (`agent/core/runner.py`)

Task execution engine:
- Retry logic with configurable attempts
- Error handling and recovery
- Tool execution with session persistence

### 5. Tools (`agent/tools/`)

21 tools organized by category:
- **Shell**: run_shell
- **Filesystem**: read_file, write_file, list_dir
- **Web**: web_search
- **Git**: git_status, git_add, git_commit, git_push, git_pull, git_checkout
- **GitHub**: run_gh
- **Self-modification**: backup_codebase, run_tests, run_agent_subprocess, request_restart
- **Planning**: create_todo, get_todo, mark_todo_done
- **Memory**: recall, remember

## Data Flow

### 1. Task Execution

```
User Input (CLI/Telegram)
    │
    ▼
AgentDeps.create(chat_id)
    │
    ├─► get_db() → SessionDB
    ├─► get_or_create_session(chat_id)
    └─► AgentDeps(session_id, db, ...)
    │
    ▼
build_session_agent()
    │
    ├─► Load tools (21)
    ├─► System prompt + memory context
    └─► Agent(deps_type=AgentDeps)
    │
    ▼
runner.run(task, deps)
    │
    ├─► agent.run(task, deps=deps)
    │       │
    │       ├─► LLM generates response
    │       ├─► Tool calls executed
    │       │       │
    │       │       └─► deps.add_tool_call()
    │       │               │
    │       │               └─► SessionDB.add_message()
    │       │
    │       └─► Return result
    │
    └─► deps.add_user_message()
    └─► deps.add_assistant_message()
```

### 2. Memory Operations

```
remember(key, category, l0, l1, l2)
    │
    ▼
AgentDeps.save_memory()
    │
    ▼
SessionDB.save_memory(entry)
    │
    ├─► INSERT INTO memory (...)
    └─► FTS5 trigger updates search index
```

```
recall(query)
    │
    ▼
AgentDeps.search_memory(query)
    │
    ▼
SessionDB.search_memory(query)
    │
    └─► SELECT FROM memory_fts WHERE memory_fts MATCH query
```

## Database Schema

### sessions

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT UNIQUE NOT NULL,  -- agent:shket:main:12345
    chat_id INTEGER,
    agent_id TEXT DEFAULT 'shket',
    scope TEXT DEFAULT 'main',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    metadata TEXT
);
```

### messages

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,           -- user/assistant/system/tool
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    tool_name TEXT,               -- For tool role
    tool_params TEXT,             -- JSON
    tool_result TEXT,
    metadata TEXT,                -- JSON
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

### memory

```sql
CREATE TABLE memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,       -- System/Environment/Skill/Project/Comm/Security
    l0_abstract TEXT NOT NULL,    -- One-line summary
    l1_overview TEXT,             -- 2-3 sentences
    l2_details TEXT,              -- Full content
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    confidence REAL DEFAULT 1.0,
    access_count INTEGER DEFAULT 0
);
```

### memory_fts (FTS5 Virtual Table)

```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
    key, category, l0_abstract, l1_overview, l2_details,
    content='memory',
    content_rowid='id'
);
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| OPENROUTER_API_KEY | OpenRouter API key | Required |
| TG_BOT_KEY | Telegram bot token | Optional |
| AGENT_MODEL | Model override | openai/gpt-oss-120b |
| AGENT_MAX_RETRIES | Max retry attempts | 3 |
| AGENT_DB_PATH | SQLite database path | data/sessions.db |

### Model Configuration

Default: OpenRouter with GPT-OSS-120B

```python
from agent.core.agent import build_session_agent

agent = build_session_agent(
    model_name="anthropic/claude-3.5-sonnet",
    api_key="your-api-key"
)
```

## Testing

```bash
# Unit tests (fast)
pytest tests/test_cli.py -v

# Session tests
pytest tests/test_session.py -v

# All tests
pytest tests/ -v
```

## References

- [OpenClaw Session Management](https://docs.openclaw.ai/concepts/session)
- [Pydantic AI Documentation](https://ai.pydantic.dev)
- [Pydantic AI Agents](https://ai.pydantic.dev/agent/)
