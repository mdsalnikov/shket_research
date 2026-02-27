"""Telegram bot interface with session support."""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from agent.activity_log import (
    log_user_message,
    log_agent_response,
    log_task_start,
    log_task_end,
    get_activity_log_tail,
)
from agent.config import LOG_FILE, TG_BOT_KEY, TG_WHITELIST, setup_logging, VERSION
from agent.session_globals import close_db

logger = logging.getLogger(__name__)

_start_time = time.time()

BOT_COMMANDS = [
    BotCommand("start", "Запустить бота / показать приветствие"),
    BotCommand("help", "Список доступных команд"),
    BotCommand("status", "Показать статус агента и время работы"),
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


_active_tasks: dict[int, TaskInfo] = {}
_task_counter = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized /start from user: %s (id=%s)", username, user.id if user else "?")
        return
    
    await update.message.reply_text(
        "🤖 Shket Research Agent online.\nSend me a task or type /help for commands."
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
    await update.message.reply_text(
        f"✅ Agent is running\n"
        f"⏱ Uptime: {h}h {m}m {s}s\n"
        f"📋 Active tasks: {n}"
    )


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
        lines.append(f"#{tid} ({elapsed}s) — {preview}")
    await update.message.reply_text("📋 Active tasks:\n" + "\n".join(lines))


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    """Show human-readable activity log."""
    n = 30
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass

    text = get_activity_log_tail(n)
    if len(text) > 4096:
        text = text[:4090] + "\n…"
    await update.message.reply_text(text)


async def exportlogs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    """Export both activity log and technical log."""
    if not os.path.exists(LOG_FILE):
        await update.message.reply_text("Log file not found.")
        return
    with open(LOG_FILE, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="agent_technical.log",
            caption="📜 Technical log (activity log is shown via /logs command)",
        )


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    
    logger.warning("/panic invoked by %s", update.effective_user.id)
    await update.message.reply_text("🛑 PANIC: halting all agent processes.")
    os._exit(1)


async def _run_agent_task(
    task_id: int,
    text: str,
    chat_id: int,
    bot,
    username: str | None = None,
    user_id: int | None = None,
) -> None:
    """Run agent task with session support and log everything."""
    task_start = time.time()
    log_task_start(task_id, text)

    reply = None
    error = None
    try:
        from agent.core.runner import run_task_with_session
        reply = await run_task_with_session(
            text,
            chat_id=chat_id,
            username=username,
            user_id=user_id,
        )
    except Exception as e:
        logger.exception("Agent error for task #%d", task_id)
        error = str(e)
        reply = f"❌ Error: {e}"
    finally:
        _active_tasks.pop(task_id, None)
        duration = time.time() - task_start
        log_task_end(task_id, error is None, duration, error)

    if len(reply) > 4096:
        reply = reply[:4090] + "\n…"

    await bot.send_message(chat_id=chat_id, text=reply)
    log_agent_response(chat_id, reply)

    from agent.tools import restart

    if restart.RESTART_REQUESTED:
        logger.info("Restart requested by agent, exec new process")
        # Close database before restart
        await close_db()
        import sys
        os.execv(sys.executable, [sys.executable, "-m", "agent", "bot"])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    # Whitelist check
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized message from user: %s (id=%s): %s", 
                      username, user.id if user else "?", 
                      update.message.text[:50] + "...")
        return
    
    global _task_counter
    text = update.message.text
    chat_id = update.effective_chat.id
    logger.info("Task from %s: %s", user.id, text)

    # Log user message
    log_user_message(chat_id, text)

    _task_counter += 1
    task_id = _task_counter
    _active_tasks[task_id] = TaskInfo(
        task_text=text,
        chat_id=chat_id,
        username=user.username if user else None,
        user_id=user.id if user else None,
    )

    await update.message.reply_text(f"⏳ Task #{task_id} accepted. Working on it…")

    asyncio.create_task(
        _run_agent_task(
            task_id,
            text,
            chat_id,
            context.bot,
            username=user.username if user else None,
            user_id=user.id if user else None,
        )
    )


async def post_init(app) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")
    
    # Log whitelist status
    if TG_WHITELIST:
        logger.info("Whitelist mode: %d allowed users", len(TG_WHITELIST))
    else:
        logger.warning("⚠️ No whitelist configured - ALL USERS ALLOWED (development mode)")


def run_bot() -> None:
    token = TG_BOT_KEY
    if not token or token.startswith("your_"):
        raise SystemExit("TG_BOT_KEY is not configured. Set it in .env or environment.")

    setup_logging()

    app = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("context", context_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("exportlogs", exportlogs_cmd))
    app.add_handler(CommandHandler("panic", panic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()
