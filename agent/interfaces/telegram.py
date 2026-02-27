import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from agent.config import LOG_FILE, TG_BOT_KEY, setup_logging, VERSION

logger = logging.getLogger(__name__)

_start_time = time.time()

BOT_COMMANDS = [
    BotCommand("start", "Запустить бота / показать приветствие"),
    BotCommand("help", "Список доступных команд"),
    BotCommand("status", "Показать статус агента и время работы"),
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
    "/tasks — список запущенных задач\n"
    "/logs \[N] — показать последние N записей лога (по умолчанию 30)\n"
    "/exportlogs — скачать полный файл лога\n"
    "/panic — экстренная остановка\n\n"
    "Отправьте любой текстовое сообщение, чтобы дать агенту задачу.\n"
    "Несколько задач могут выполняться одновременно — бот остаётся отзывчивым.\n\n"
    "*Доступные инструменты:*\n"
    "🐚 Shell, 📁 Filesystem, 🌐 Web search\n"
    "📋 TODO, 🔄 Backup & self-test, 📦 Git (commit/push), 🔁 Restart"
    f"\n\nВерсия: {VERSION}"
)


@dataclass
class TaskInfo:
    task_text: str
    chat_id: int
    started: float = field(default_factory=time.time)


_active_tasks: dict[int, TaskInfo] = {}
_task_counter = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Shket Research Agent online.\nSend me a task or type /help for commands."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime = int(time.time() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    n = len(_active_tasks)
    await update.message.reply_text(
        f"✅ Agent is running\n"
        f"⏱ Uptime: {h}h {m}m {s}s\n"
        f"📋 Active tasks: {n}"
    )


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    n = 30
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass

    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        await update.message.reply_text("Log file not found.")
        return

    tail = lines[-n:] if len(lines) > n else lines
    header = f"📜 Last {len(tail)} of {len(lines)} log entries:\n\n"
    text = header + "".join(tail)
    if len(text) > 4096:
        text = text[:4090] + "\n…"
    await update.message.reply_text(text)


async def exportlogs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not os.path.exists(LOG_FILE):
        await update.message.reply_text("Log file not found.")
        return
    with open(LOG_FILE, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="agent.log",
            caption="📜 Full agent log",
        )


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("/panic invoked by %s", update.effective_user.id)
    await update.message.reply_text("🛑 PANIC: halting all agent processes.")
    os._exit(1)


async def _run_agent_task(task_id: int, text: str, chat_id: int, bot) -> None:
    try:
        from agent.core.runner import run_with_retry

        reply = await run_with_retry(text)
    except Exception as e:
        logger.exception("Agent error for task #%d", task_id)
        reply = f"❌ Error: {e}"
    finally:
        _active_tasks.pop(task_id, None)

    if len(reply) > 4096:
        reply = reply[:4090] + "\n…"
    await bot.send_message(chat_id=chat_id, text=reply)

    from agent.tools import restart

    if restart.RESTART_REQUESTED:
        logger.info("Restart requested by agent, exec new process")
        import sys

        os.execv(sys.executable, [sys.executable, "-m", "agent", "bot"])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _task_counter
    text = update.message.text
    chat_id = update.effective_chat.id
    logger.info("Task from %s: %s", update.effective_user.id, text)

    _task_counter += 1
    task_id = _task_counter
    _active_tasks[task_id] = TaskInfo(task_text=text, chat_id=chat_id)

    await update.message.reply_text(f"⏳ Task #{task_id} accepted. Working on it…")

    asyncio.create_task(_run_agent_task(task_id, text, chat_id, context.bot))


async def post_init(app) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")


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
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("exportlogs", exportlogs_cmd))
    app.add_handler(CommandHandler("panic", panic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()
