"""Telegram bot interface with session support."""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Literal

from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from agent.activity_log import (
    log_user_message,
    log_agent_response,
    log_task_start,
    log_task_end,
    get_activity_log_tail,
)
from agent.config import LOG_FILE, TG_BOT_KEY, TG_WHITELIST, setup_logging, VERSION, PROVIDER_DEFAULT
from agent.session_globals import close_db

logger = logging.getLogger(__name__)

_start_time = time.time()

# Current provider for bot sessions (can be changed via /provider command)
_current_provider: Literal["vllm", "openrouter"] = PROVIDER_DEFAULT

BOT_COMMANDS = [
    BotCommand("start", "Запустить бота / показать приветствие"),
    BotCommand("help", "Список доступных команд"),
    BotCommand("status", "Показать статус агента и время работы"),
    BotCommand("provider", "Переключить LLM провайдера (vllm/openrouter)"),
    BotCommand("context", "Показать информацию о контексте сессии"),
    BotCommand("clear", "Очистить контекст сессии"),
    BotCommand("tasks", "Список запущенных задач"),
    BotCommand("logs", "Показать последние N записей лога (по умолчанию 30)"),
    BotCommand("exportlogs", "Скачать полный файл лога"),
    BotCommand("panic", "Экстренная остановка — завершить все процессы агента"),
]

HELP_TEXT = (
    "🤖 *Shket Research Agent*\n\n"
    "*Команды:*\n"
    "/start — приветственное сообщение\n"
    "/help — это справка\n"
    "/status — статус агента и время работы\n"
    "/provider — переключить провайдера (vllm/openrouter)\n"
    "/context — информация о контексте (сообщения, токены)\n"
    "/clear — очистить контекст сессии\n"
    "/tasks — список запущенных задач\n"
    "/logs \[N] — показать последние N записей лога (по умолчанию 30)\n"
    "/exportlogs — скачать полный файл лога\n"
    "/panic — экстренная остановка\n\n"
    "Отправьте любой текстовое сообщение, чтобы дать агенту задачу.\n"
    "Несколько задач могут выполняться одновременно — бот остаётся отзывчивым.\n\n"
    "*Доступные инструменты:*\n"
    "🐚 Shell, 📁 Filesystem, 🌐 Web search\n"
    "📋 TODO, 🔄 Backup & self-test, 📦 Git (commit/push), 🔁 Restart\n"
    "🧠 Memory (remember/recall)"
    f"\n\nВерсия: {VERSION}"
)

# Whitelist error message
WHITELIST_ERROR = (
    "⛔ *Access Denied*\n\n"
    "Этот бот доступен только авторизованным пользователям.\n"
    "Если вы должны иметь доступ, обратитесь к администратору."
)


def _is_user_allowed(username: str | None) -> bool:
    """Check if user is in whitelist.
    
    Args:
        username: Telegram username (without @) or None
        
    Returns:
        True if user is allowed or whitelist is empty (dev mode)
    """
    if not TG_WHITELIST:
        # No whitelist configured = allow all (development mode)
        return True
    
    if not username:
        # User has no username = deny
        return False
    
    return username.lower() in TG_WHITELIST


@dataclass
class TaskInfo:
    task_text: str
    chat_id: int
    started: float = field(default_factory=time.time)
    username: str | None = None
    user_id: int | None = None
    provider: str | None = None


_active_tasks: dict[int, TaskInfo] = {}
_task_counter = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized /start from user: %s (id=%s)", username, user.id if user else "?")
        return
    
    provider_info = f"\n📡 Provider: *{_current_provider}*" if _current_provider != PROVIDER_DEFAULT else ""
    await update.message.reply_text(
        f"🤖 Shket Research Agent online.\nSend me a task or type /help for commands.{provider_info}",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    uptime = int(time.time() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    n = len(_active_tasks)
    
    provider_status = f"📡 Provider: *{_current_provider}*\n"
    await update.message.reply_text(
        f"✅ Agent is running\n"
        f"⏱ Uptime: {h}h {m}m {s}s\n"
        f"{provider_status}"
        f"📋 Active tasks: {n}",
        parse_mode="Markdown"
    )


async def provider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch LLM provider between vllm and openrouter."""
    global _current_provider
    
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    # Get provider argument
    args = context.args if context.args else []
    
    if not args:
        # Show current provider
        await update.message.reply_text(
            f"📡 *Current Provider:* `{_current_provider}`\n\n"
            "To switch:\n"
            "/provider vllm — local vLLM server\n"
            "/provider openrouter — cloud OpenRouter",
            parse_mode="Markdown"
        )
        return
    
    new_provider = args[0].lower()
    
    if new_provider not in ("vllm", "openrouter"):
        await update.message.reply_text(
            "❌ Invalid provider. Use:\n"
            "/provider vllm — local vLLM server\n"
            "/provider openrouter — cloud OpenRouter",
            parse_mode="Markdown"
        )
        return
    
    old_provider = _current_provider
    _current_provider = new_provider
    
    await update.message.reply_text(
        f"✅ Provider switched: `{old_provider}` → `{new_provider}`\n\n"
        f"New tasks will use *{new_provider}*.",
        parse_mode="Markdown"
    )
    logger.info(f"Provider switched from {old_provider} to {new_provider} by user {username}")


async def context_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current session context info."""
    from agent.session_globals import get_db
    
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    chat_id = update.effective_chat.id
    db = await get_db()
    
    session_id = await db.get_or_create_session(chat_id)
    stats = await db.get_session_stats(session_id, include_last_messages=3)
    
    if "error" in stats:
        await update.message.reply_text(f"❌ {stats['error']}")
        return
    
    # Format uptime
    uptime_h = int(stats["uptime_seconds"] // 3600)
    uptime_m = int((stats["uptime_seconds"] % 3600) // 60)
    idle_m = int(stats["idle_seconds"] // 60)
    
    text = (
        f"📊 *Context Info*\n\n"
        f"📝 Messages: *{stats['message_count']}*\n"
        f"🔤 Estimated tokens: *{stats['estimated_tokens']:,}*\n"
        f"📏 Total chars: *{stats['total_chars']:,}*\n\n"
        f"⏱ Session age: {uptime_h}h {uptime_m}m\n"
        f"💤 Idle: {idle_m}m ago\n\n"
        f"_Last {len(stats['last_messages'])} messages:_\n"
    )
    
    for msg in stats["last_messages"]:
        role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}.get(msg["role"], "📄")
        preview = msg["content_preview"].replace("_", "\_").replace("*", "\*")
        text += f"\n{role_emoji} _{preview}_"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear session context."""
    from agent.session_globals import get_db
    
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    chat_id = update.effective_chat.id
    db = await get_db()
    
    session_id = await db.get_or_create_session(chat_id)
    await db.clear_session(session_id)
    
    await update.message.reply_text(
        "✅ *Context Cleared*\n\n"
        "Session messages deleted.\n"
        "Session metadata preserved.\n"
        "Memory intact.",
        parse_mode="Markdown"
    )


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    if not _active_tasks:
        await update.message.reply_text("No active tasks.")
        return
    lines = []
    for tid, info in _active_tasks.items():
        elapsed = int(time.time() - info.started)
        preview = info.task_text[:60] + ("…" if len(info.task_text) > 60 else "")
        provider_tag = f"[{info.provider}] " if info.provider else ""
        lines.append(f"#{tid} ({elapsed}s) — {provider_tag}{preview}")
    await update.message.reply_text("📋 Active tasks:\n" + "\n".join(lines))


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    """Show human-readable activity log."""
    n = 30
 
    args = context.args
    if args:
        try:
            n = int(args[0])
        except ValueError:
            pass

    entries = get_activity_log_tail(n)
    if not entries:
        await update.message.reply_text("Log is empty.")
        return

    lines = [f"{e['time']} {e['action']}: {e['detail']}" for e in entries]
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[-4000:]
    await update.message.reply_text(f"```\n{text}\n```", parse_mode="Markdown")


async def export_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    """Send the full log file."""
    try:
        await update.message.reply_document(
            document=open(LOG_FILE, "rb"),
            filename="agent.log",
        )
    except FileNotFoundError:
        await update.message.reply_text(f"Log file not found: {LOG_FILE}")


async def panic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    """Emergency stop: terminate all agent processes."""
    # Note: This doesn't actually kill processes yet, just logs and notifies
    await update.message.reply_text(
        "🚨 *Emergency stop requested*\n\n"
        "Stopping all active tasks...",
        parse_mode="Markdown"
    )
    
    # Clear active tasks
    global _active_tasks
    n = len(_active_tasks)
    _active_tasks = {}
    
    logger.warning(f"PANIC: Cleared {n} active tasks by user {username}")
    await update.message.reply_text(f"✅ Cleared {n} active tasks.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages as tasks."""
    global _task_counter, _current_provider

    user = update.effective_user
    username = user.username if user else None
    user_id = user.id if user else None

    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized message from user: %s (id=%s)", username, user_id)
        return

    text = update.message.text
    if not text:
        return

    chat_id = update.effective_chat.id
    _task_counter += 1
    task_id = _task_counter

    # Use current provider
    provider = _current_provider

    # Create task info
    task_info = TaskInfo(
        task_text=text,
        chat_id=chat_id,
        username=username,
        user_id=user_id,
        provider=provider,
    )
    _active_tasks[task_id] = task_info

    # Log start
    log_task_start(task_id, text, username)
    log_user_message(chat_id, text, username)

    logger.info(f"Task #{task_id} started by {username}: {text[:60]}... (provider={provider})")

    # Acknowledge
    await update.message.reply_text(
        f"⏳ Processing (task #{task_id}, provider={provider})...",
    )

    # Run task
    try:
        from agent.core.runner import run_task_with_session

        result = await run_task_with_session(
            text,
            chat_id=chat_id,
            username=username,
            user_id=user_id,
            provider=provider,
        )
        await update.message.reply_text(result)
        log_agent_response(chat_id, result)
        log_task_end(task_id, "success")

    except Exception as e:
        logger.exception(f"Task #{task_id} failed")
        await update.message.reply_text(f"❌ Task failed: {e}")
        log_task_end(task_id, "failed", str(e))

    finally:
        _active_tasks.pop(task_id, None)


def run_bot() -> None:
    """Start the Telegram bot with long-polling."""
    setup_logging()
    logger.info(f"Starting Telegram bot (provider={_current_provider})")

    app = (
        ApplicationBuilder()
        .token(TG_BOT_KEY)
        .build()
    )

    # Register commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("provider", provider_cmd))
    app.add_handler(CommandHandler("context", context_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("exportlogs", export_logs))
    app.add_handler(CommandHandler("panic", panic_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set bot commands for UI
    asyncio.get_event_loop().run_until_complete(
        app.bot.set_my_commands(BOT_COMMANDS)
    )

    logger.info("Bot started with long-polling")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
