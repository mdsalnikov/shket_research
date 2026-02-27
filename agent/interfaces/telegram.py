import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from agent.config import TG_BOT_KEY

logger = logging.getLogger(__name__)

_start_time = time.time()

BOT_COMMANDS = [
    BotCommand("start", "Start the bot / show welcome message"),
    BotCommand("help", "List available commands"),
    BotCommand("status", "Show agent status and uptime"),
    BotCommand("tasks", "List running tasks"),
    BotCommand("panic", "Emergency halt — kill all agent processes"),
]

HELP_TEXT = (
    "🤖 *Shket Research Agent*\n\n"
    "*Commands:*\n"
    "/start — welcome message\n"
    "/help — this help\n"
    "/status — agent status & uptime\n"
    "/tasks — list running tasks\n"
    "/panic — emergency halt\n\n"
    "Send any text message to give the agent a task.\n"
    "Multiple tasks run concurrently — the bot stays responsive.\n\n"
    "*Available tools:*\n"
    "🐚 Shell — execute OS commands\n"
    "🌐 Web search — search the internet\n"
    "📁 Filesystem — read / write / list files\n"
    "🔍 Deep Research — multi-step web research"
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


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning("/panic invoked by %s", update.effective_user.id)
    await update.message.reply_text("🛑 PANIC: halting all agent processes.")
    os._exit(1)


async def _run_agent_task(task_id: int, text: str, chat_id: int, bot) -> None:
    try:
        from agent.core.agent import build_agent

        agent = build_agent()
        result = await agent.run(text)
        reply = result.output
    except Exception as e:
        logger.exception("Agent error for task #%d", task_id)
        reply = f"❌ Error: {e}"
    finally:
        _active_tasks.pop(task_id, None)

    if len(reply) > 4096:
        reply = reply[:4090] + "\n…"
    await bot.send_message(chat_id=chat_id, text=reply)


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

    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

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
    app.add_handler(CommandHandler("panic", panic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()
