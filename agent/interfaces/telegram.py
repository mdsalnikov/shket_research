"""Telegram bot interface with session support and progress tracking."""

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
from agent.config import (
    LOG_FILE,
    OPENROUTER_API_KEY,
    TG_BOT_KEY,
    TG_WHITELIST,
    setup_logging,
    VERSION,
    PROVIDER_DEFAULT,
)
from agent.session_globals import close_db
from agent.progress import get_tracker

logger = logging.getLogger(__name__)

_start_time = time.time()


def _effective_provider() -> Literal["vllm", "openrouter"]:
    """Use vLLM when OpenRouter is selected but API key is missing."""
    if PROVIDER_DEFAULT == "openrouter" and not OPENROUTER_API_KEY:
        return "vllm"
    return PROVIDER_DEFAULT  # type: ignore[return-value]


# Current provider for bot sessions (can be changed via /provider command)
_current_provider: Literal["vllm", "openrouter"] = _effective_provider()

# Grouped for menu: main, tasks, session, logs, emergency
BOT_COMMANDS = [
    BotCommand("start", "Приветствие"),
    BotCommand("help", "Справка по командам (группы)"),
    BotCommand("status", "Статус агента и uptime"),
    BotCommand("tasks", "Запущенные задачи и очередь"),
    BotCommand("long", "Запустить long-задачу (возобновляется после рестарта)"),
    BotCommand("longlist", "Список long-задач этого чата (running/completed/failed)"),
    BotCommand("provider", "Провайдер LLM (vllm/openrouter)"),
    BotCommand("context", "Контекст сессии (сообщения, токены)"),
    BotCommand("clear", "Очистить контекст сессии"),
    BotCommand("logs", "Последние N записей лога"),
    BotCommand("exportlogs", "Скачать полный лог"),
    BotCommand("panic", "Экстренная остановка"),
]

HELP_TEXT = (
    "🤖 *Shket Research Agent*\n\n"
    "*Основные:*\n"
    "/start — приветствие\n"
    "/help — эта справка\n"
    "/status — статус агента, uptime, resumable\n\n"
    "*Задачи:*\n"
    "/tasks — запущенные задачи и очередь по чатам\n"
    "/long _цель_ — long‑задача (переживёт рестарт бота)\n"
    "/longlist — список long‑задач этого чата (running/completed/failed)\n\n"
    "*Сессия:*\n"
    "/provider — vllm | openrouter\n"
    "/context — сообщения, токены\n"
    "/clear — очистить контекст\n\n"
    "*Логи:*\n"
    r"/logs \[N] — последние N строк (по умолчанию 30)" + "\n"
    "/exportlogs — скачать лог\n\n"
    "*Экстренно:* /panic\n\n"
    "Любое текстовое сообщение — задача агенту. Несколько задач параллельно.\n\n"
    "*Инструменты:* Shell, Filesystem, Web, TODO, Backup, Git, Memory\n\n"
    "⚡ *Прогресс:* Вы будете видеть обновления на каждом шаге задачи!"
    f"\n\nВерсия: {VERSION}"
)

# Telegram limit is 4096; use slightly less for safety
MAX_MESSAGE_LENGTH = 4090

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


MAX_RESUME_COUNT = 5


async def _send_progress_update(chat_id: int, message: str) -> None:
    """Send progress update to Telegram chat.
    
    This is the callback used by ProgressTracker to send updates.
    
    Args:
        chat_id: Telegram chat ID
        message: Progress update message
    """
    try:
        # Get the bot instance from application
        bot = application.bot
        await _send_long_to_chat(bot, chat_id, f"\n{message}\n")
    except Exception as e:
        logger.error("Failed to send progress update to chat %s: %s", chat_id, e)


async def _send_long_message(message, text: str) -> None:
    """Send text in chunks so each message stays under Telegram's 4096 limit."""
    text = str(text) if not isinstance(text, str) else text
    while text:
        if len(text) <= MAX_MESSAGE_LENGTH:
            await message.reply_text(text)
            return
        chunk = text[:MAX_MESSAGE_LENGTH]
        last_nl = chunk.rfind("\n")
        if last_nl != -1:
            chunk = chunk[: last_nl + 1]
        await message.reply_text(chunk)
        text = text[len(chunk) :]


async def _send_long_to_chat(bot, chat_id: int, text: str) -> None:
    """Send long text to chat in chunks (for resume when no message object)."""
    text = str(text) if not isinstance(text, str) else text
    while text:
        if len(text) <= MAX_MESSAGE_LENGTH:
            await bot.send_message(chat_id=chat_id, text=text)
            return
        chunk = text[:MAX_MESSAGE_LENGTH]
        last_nl = chunk.rfind("\n")
        if last_nl != -1:
            chunk = chunk[: last_nl + 1]
        await bot.send_message(chat_id=chat_id, text=chunk)
        text = text[len(chunk) :]


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
_chat_locks: dict[int, asyncio.Lock] = {}
_chat_queued_count: dict[int, int] = {}


def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    """Return per-chat lock so tasks in the same chat run one after another."""
    if chat_id not in _chat_locks:
        _chat_locks[chat_id] = asyncio.Lock()
    return _chat_locks[chat_id]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized /start from user: %s (id=%s)", username, user.id if user else "?")
        return
    
    provider_info = f"\n📡 Provider: *{_current_provider}*" if _current_provider != _effective_provider() else ""
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
    running = len(_active_tasks)
    queued = sum(_chat_queued_count.values())
    resumable_n = 0
    try:
        from agent.session_globals import get_db
        db = await get_db()
        resumable_n = len(await db.get_incomplete_resumable_tasks())
    except Exception:
        pass
    provider_status = f"📡 Provider: *{_current_provider}*\n"
    resumable_line = f"\n📌 Resumable: {resumable_n} (will resume on next startup)" if resumable_n else ""
    await update.message.reply_text(
        f"✅ Agent is running\n"
        f"⏱ Uptime: {h}h {m}m {s}s\n"
        f"{provider_status}"
        f"📋 Active: {running} running, {queued} queued"
        f"{resumable_line}",
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
        await update.message.reply_text(
            f"Current provider: *{_current_provider}*\nUsage: /provider vllm|openrouter",
            parse_mode="Markdown"
        )
        return
    
    provider = args[0].lower()
    if provider not in ("vllm", "openrouter"):
        await update.message.reply_text(
            "Invalid provider. Use: /provider vllm|openrouter",
            parse_mode="Markdown"
        )
        return
    
    if provider == "openrouter" and not OPENROUTER_API_KEY:
        await update.message.reply_text(
            "OpenRouter API key not configured. Using vllm.",
            parse_mode="Markdown"
        )
        return
    
    _current_provider = provider  # type: ignore[assignment]
    await update.message.reply_text(
        f"✅ Provider changed to: *{_current_provider}*",
        parse_mode="Markdown"
    )


# Global application reference for progress updates
application: ApplicationBuilder | None = None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages as tasks."""
    global _task_counter
    
    user = update.effective_user
    username = user.username if user else None
    chat_id = update.effective_chat.id
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized message from user: %s (id=%s)", username, user.id if user else "?")
        return
    
    task_text = update.message.text
    
    # Configure progress tracker for this chat
    tracker = get_tracker(chat_id=chat_id, is_cli=False)
    tracker.telegram_callback = _send_progress_update
    
    # Create task info
    _task_counter += 1
    task_info = TaskInfo(
        task_text=task_text,
        chat_id=chat_id,
        username=username,
        user_id=user.id,
        provider=_current_provider,
    )
    _active_tasks[_task_counter] = task_info
    
    # Acquire chat lock
    lock = _get_chat_lock(chat_id)
    
    # Check queue
    if _chat_queued_count.get(chat_id, 0) > 0:
        await update.message.reply_text(
            f"⏳ Task queued ({_chat_queued_count[chat_id]} ahead)",
            parse_mode="Markdown"
        )
    
    async with lock:
        _chat_queued_count[chat_id] = 0
        
        # Log task start
        log_task_start(task_text, chat_id, username)
        
        try:
            # Run task with session
            from agent.core.runner import run_task_with_session
            
            result = await run_task_with_session(
                task_text,
                chat_id=chat_id,
                username=username,
                user_id=user.id,
                provider=_current_provider,
            )
            
            # Send result
            await _send_long_message(update.message, result)
            
            # Log task end
            log_task_end(task_text, chat_id, username, success=True)
            
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            await update.message.reply_text(error_msg, parse_mode="Markdown")
            
            # Log task end
            log_task_end(task_text, chat_id, username, success=False, error=str(e))
            
            logger.exception("Task failed for chat_id=%s", chat_id)
    
    # Clean up
    del _active_tasks[_task_counter]


def run_bot() -> None:
    """Run Telegram bot."""
    global application
    
    if not TG_BOT_KEY:
        logger.error("TG_BOT_KEY not set. Cannot start Telegram bot.")
        return
    
    setup_logging()
    
    # Create application
    application = (
        ApplicationBuilder()
        .token(TG_BOT_KEY)
        .enable_coroutine_support()
        .build()
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("provider", provider_cmd))
    
    # Add message handler (for tasks)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Telegram bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
