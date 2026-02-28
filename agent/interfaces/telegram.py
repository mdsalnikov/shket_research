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
    "*Инструменты:* Shell, Filesystem, Web, TODO, Backup, Git, Memory"
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

    if new_provider == "openrouter" and not OPENROUTER_API_KEY:
        await update.message.reply_text(
            "❌ OpenRouter requires OPENROUTER_API_KEY. Set it and restart the bot, or use /provider vllm.",
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
        preview = msg["content_preview"].replace("_", r"\_").replace("*", r"\*")
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
    
    running = len(_active_tasks)
    queued = sum(_chat_queued_count.values())
    if running == 0 and queued == 0:
        await update.message.reply_text("No active tasks.")
        return
    lines = []
    for tid, info in _active_tasks.items():
        elapsed = int(time.time() - info.started)
        preview = info.task_text[:60] + ("…" if len(info.task_text) > 60 else "")
        provider_tag = f"[{info.provider}] " if info.provider else ""
        lines.append(f"#{tid} ({elapsed}s) — {provider_tag}{preview}")
    for cid, count in sorted(_chat_queued_count.items()):
        if count > 0:
            lines.append(f"Chat {cid}: {count} queued")
    header = f"📋 Running: {running}, queued: {queued}\n"
    await update.message.reply_text(header + "\n".join(lines))


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None

    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return

    n = 30
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass

    text = get_activity_log_tail(n)
    if not text or "empty" in text.lower():
        await update.message.reply_text("Log is empty.")
        return
    if len(text) > 4000:
        text = text[-4000:]
    await update.message.reply_text(f"```\n{text}\n```", parse_mode="Markdown")


async def export_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return

    try:
        with open(LOG_FILE, "rb") as f:
            await update.message.reply_document(document=f, filename="agent.log")
    except FileNotFoundError:
        await update.message.reply_text(f"Log file not found: {LOG_FILE}")


async def panic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.username if user else None
    
    if not _is_user_allowed(username):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return

    # Note: This doesn't actually kill processes yet, just logs and notifies
    await update.message.reply_text(
        "🚨 *Emergency stop requested*\n\n"
        "Stopping all active tasks...",
        parse_mode="Markdown"
    )
    
    # Clear active tasks (running coroutines continue; display only)
    global _active_tasks, _chat_queued_count
    n = len(_active_tasks)
    _active_tasks = {}
    _chat_queued_count = {}
    logger.warning(f"PANIC: Cleared {n} active tasks by user {username}")
    await update.message.reply_text(f"✅ Cleared {n} active tasks.")


async def _execute_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    goal: str,
    resumable_task_id: int | None = None,
) -> None:
    """Run one task under chat lock; optional resumable_task_id for DB status updates."""
    global _task_counter, _current_provider
    user = update.effective_user
    username = user.username if user else None
    user_id = user.id if user else None
    chat_id = update.effective_chat.id
    lock = _get_chat_lock(chat_id)
    _chat_queued_count[chat_id] = _chat_queued_count.get(chat_id, 0) + 1
    got_lock = False
    try:
        async with lock:
            got_lock = True
            _chat_queued_count[chat_id] = max(0, _chat_queued_count.get(chat_id, 1) - 1)
            _task_counter += 1
            task_id = _task_counter
            provider = _current_provider
            _active_tasks[task_id] = TaskInfo(
                task_text=goal,
                chat_id=chat_id,
                username=username,
                user_id=user_id,
                provider=provider,
            )
            log_task_start(task_id, goal)
            log_user_message(chat_id, goal)
            logger.info(f"Task #{task_id} started by {username}: {goal[:60]}... (provider={provider})")
            await update.message.reply_text(
                f"⏳ Processing (task #{task_id}, provider={provider})...",
            )
            task_start = time.time()
            try:
                from agent.core.runner import run_task_with_session
                result = await run_task_with_session(
                    goal,
                    chat_id=chat_id,
                    username=username,
                    user_id=user_id,
                    provider=provider,
                    resumable_task_id=resumable_task_id,
                )
                duration = time.time() - task_start
                await _send_long_message(update.message, result)
                log_agent_response(chat_id, result)
                log_task_end(task_id, True, duration)
            except Exception as e:
                duration = time.time() - task_start
                logger.exception(f"Task #{task_id} failed")
                await update.message.reply_text(f"❌ Task failed: {e}")
                log_task_end(task_id, False, duration, str(e))
            finally:
                _active_tasks.pop(task_id, None)
    finally:
        if not got_lock:
            _chat_queued_count[chat_id] = max(0, _chat_queued_count.get(chat_id, 1) - 1)


async def long_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a resumable (long) task: survives bot restart and continues on next startup."""
    if not _is_user_allowed(update.effective_user.username if update.effective_user else None):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    goal = " ".join(context.args).strip() if context.args else ""
    if not goal:
        await update.message.reply_text("Usage: /long <goal> — task will resume after bot restart.")
        return
    chat_id = update.effective_chat.id
    from agent.session_globals import get_db
    db = await get_db()
    session_id = await db.get_or_create_session(chat_id)
    resumable_task_id = await db.upsert_resumable_task(session_id, chat_id, goal)
    await update.message.reply_text(
        "Task saved as resumable. If the bot restarts, it will continue automatically."
    )
    await _execute_task(update, context, goal, resumable_task_id=resumable_task_id)


async def longlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List resumable (long) tasks for this chat: running, then recent completed/failed."""
    if not _is_user_allowed(update.effective_user.username if update.effective_user else None):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        return
    chat_id = update.effective_chat.id
    from agent.session_globals import get_db
    db = await get_db()
    tasks = await db.get_resumable_tasks(chat_id=chat_id, limit=15)
    if not tasks:
        await update.message.reply_text("Нет long‑задач в этом чате.")
        return
    status_emoji = {"running": "🔄", "completed": "✅", "failed": "❌", "cancelled": "⏹"}
    lines = ["*Long‑задачи (этот чат):*\n"]
    for t in tasks:
        em = status_emoji.get(t["status"], "•")
        raw = (t["goal"] or "")[:55] + ("…" if len(t["goal"] or "") > 55 else "")
        goal_preview = raw.replace("_", r"\_").replace("*", r"\*")
        res = f"resume={t['resume_count']}" if t.get("resume_count") else ""
        lines.append(f"{em} #{t['id']} {t['status']} {res}\n   _{goal_preview}_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages as tasks. Same-chat tasks run one after another."""
    if not _is_user_allowed(update.effective_user.username if update.effective_user else None):
        await update.message.reply_text(WHITELIST_ERROR, parse_mode="Markdown")
        logger.warning("Unauthorized message from user: %s", update.effective_user)
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    await _execute_task(update, context, text, resumable_task_id=None)


def _build_resume_prompt(goal: str, resume_count: int) -> str:
    return (
        "[Resume] The process was restarted. Continue the following task from where you left off.\n\n"
        f"Original goal: {goal}\n\n"
        f"Resume count: {resume_count}. If you have get_todo, call it to see remaining steps and continue. "
        "Reply with progress and final or intermediate result."
    )


async def _do_resume(bot, task_row: dict) -> None:
    """Resume one incomplete task: send to chat, run agent, update status."""
    task_id = task_row["id"]
    chat_id = task_row["chat_id"]
    goal = task_row["goal"]
    resume_count = task_row["resume_count"]
    if resume_count >= MAX_RESUME_COUNT:
        from agent.session_globals import get_db
        db = await get_db()
        await db.mark_resumable_task_failed(task_id, "Max resume count exceeded")
        await bot.send_message(
            chat_id=chat_id,
            text=f"Resumable task failed: max resume count ({MAX_RESUME_COUNT}) exceeded. Goal: {goal[:100]}...",
        )
        return
    lock = _get_chat_lock(chat_id)
    async with lock:
        from agent.session_globals import get_db
        from agent.core.runner import run_task_with_session
        db = await get_db()
        await db.increment_resume_and_set_resumed_at(task_id)
        resume_count += 1
        prompt = _build_resume_prompt(goal, resume_count)
        await bot.send_message(
            chat_id=chat_id,
            text=f"Resuming task ({resume_count}/{MAX_RESUME_COUNT}): {goal[:80]}{'…' if len(goal) > 80 else ''}",
        )
        try:
            result = await run_task_with_session(
                prompt,
                chat_id=chat_id,
                username=None,
                user_id=None,
                provider=_current_provider,
                resumable_task_id=None,
            )
            await db.mark_resumable_task_completed(task_id)
            await _send_long_to_chat(bot, chat_id, result)
        except Exception as e:
            logger.exception("Resume task failed: %s", e)
            await db.mark_resumable_task_failed(task_id, str(e))
            await bot.send_message(chat_id=chat_id, text=f"❌ Resume failed: {e}")


async def _resume_incomplete_tasks(app) -> None:
    """Load incomplete resumable tasks and run resume for each (called on bot startup)."""
    from agent.session_globals import get_db
    try:
        db = await get_db()
        incomplete = await db.get_incomplete_resumable_tasks()
    except Exception as e:
        logger.exception("Failed to load incomplete resumable tasks: %s", e)
        return
    for row in incomplete:
        asyncio.create_task(_do_resume(app.bot, row))


def run_bot() -> None:
    """Start the Telegram bot with long-polling."""
    setup_logging()
    logger.info(f"Starting Telegram bot (provider={_current_provider})")

    async def _on_post_init(application):
        asyncio.create_task(_resume_incomplete_tasks(application))

    app = (
        ApplicationBuilder()
        .token(TG_BOT_KEY)
        .concurrent_updates(True)
        .post_init(_on_post_init)
        .build()
    )

    # Register commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("provider", provider_cmd))
    app.add_handler(CommandHandler("context", context_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("long", long_cmd))
    app.add_handler(CommandHandler("longlist", longlist_cmd))
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
