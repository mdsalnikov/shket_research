## Summary

Добавлена команда `python -m agent context` для отображения информации о текущей сессии.

## Changes

- **New command**: `python -m agent context`
- Shows session statistics:
  - Message count
  - Estimated tokens
  - Total characters
- Displays timing info:
  - Session created timestamp
  - Last activity timestamp
  - Session age (uptime)
  - Idle time
- Shows last 5 messages with role emojis and content previews

## Usage

```bash
python -m agent context

=== Session Context ===

📝 Messages: 42
🔤 Estimated tokens: 12,345
📏 Total chars: 45,678

⏱ Session created: 2025-02-27 20:00:00
🕐 Last activity: 2025-02-27 21:30:00
   Session age: 1h 30m
   Idle: 5m ago

--- Last 5 messages ---

👤 [user] (123 chars)
   Привет, как дела?

🤖 [assistant] (456 chars)
   Привет! Всё отлично...
```

## Testing

All tests pass:
- test_agent_status ✓
- test_agent_help ✓

## Version

0.0.6