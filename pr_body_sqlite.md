## Summary

This PR documents the SQLite + Pydantic AI architecture that's already implemented in the codebase. The architecture follows OpenClaw-inspired session management patterns.

## Architecture Highlights

### Session Management (OpenClaw-inspired)
- **Session Key Format**: `agent:<agentId>:<scope>:<chatId>`
- **Session Scopes**: main, per-peer, per-channel-peer
- **SQLite Persistence**: All sessions stored in `data/sessions.db`

### Memory Hierarchy (L0/L1/L2)
- **L0 (Abstract)**: One-line summary for quick scanning
- **L1 (Overview)**: 2-3 sentence context
- **L2 (Details)**: Full content for deep retrieval
- **Categories**: System, Environment, Skill, Project, Comm, Security
- **FTS5 Search**: Full-text search for memory

### Pydantic AI Integration
- `AgentDeps` dependency injection container
- `build_session_agent()` for full session support
- Dynamic system prompt with memory context
- 21 tools integrated with session persistence

## Components

| Component | File | Purpose |
|-----------|------|---------|
| SessionDB | `agent/session_db.py` | SQLite storage layer |
| Session | `agent/session.py` | Data models (SessionMessage, MemoryEntry) |
| AgentDeps | `agent/dependencies.py` | Dependency injection for Pydantic AI |
| Agent | `agent/core/agent.py` | Pydantic AI agent builder |
| Runner | `agent/core/runner.py` | Task execution engine |
| Tools | `agent/tools/` | 21 tools with session support |

## Tests

All 57 tests pass:
- `test_session.py` - 15 session tests
- `test_dependencies.py` - 14 dependency tests
- `test_runner.py` - 3 runner tests
- Plus 25 other tests

## Documentation

Added `docs/ARCHITECTURE.md` with:
- Architecture diagram
- Data flow documentation
- Database schema reference
- Component descriptions
- Configuration guide

## Related

- OpenClaw Session Management: https://docs.openclaw.ai/concepts/session
- Pydantic AI: https://ai.pydantic.dev
