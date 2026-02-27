import logging
import os
import time

from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from agent.config import TG_BOT_KEY

logger = logging.getLogger(__name__)

_start_time = time.time()

BOT_COMMANDS = [
    BotCommand("start", "Start the bot / show welcome message"),
    BotCommand("help", "List available commands"),
    BotCommand("status", "Show agent status and uptime"),
    BotCommand("panic", "Emergency halt — kill all agent processes"),
]

HELP_TEXT = (
    "🤖 *Shket Research Agent*\n\n"
    "*Commands:*\n"
    "/start — welcome message\n"
    "/help — this help\n"
    "/status — agent status & uptime\n"
    "/panic — emergency halt\n\n"
    "Send any text message to give the agent a task.\n\n"
    "*Available tools:*\n"
    "🐚 Shell — execute OS commands\n"
    "🌐 Web search — search the internet\n"
    "📁 Filesystem — read / write / list files\n"
    "🔍 Deep Research — multi-step web research"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Shket Research Agent online.\nSend me a task or type /help for commands."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime = int(time.time() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    await update.message.reply_text(
        f"✅ Agent is running\n⏱ Uptime: {h}h {m}m {s}s"
    )


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning("/panic invoked by %s", update.effective_user.id)
    await update.message.reply_text("🛑 PANIC: halting all agent processes.")
    os._exit(1)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    logger.info("Task from %s: %s", update.effective_user.id, text)
    await update.message.reply_text("⏳ Working on it…")

    try:
        from agent.core.agent import build_agent

        agent = build_agent()
        result = await agent.run(text)
        reply = result.output
    except Exception as e:
        logger.exception("Agent error")
        reply = f"❌ Error: {e}"

    if len(reply) > 4096:
        reply = reply[:4090] + "\n…"
    await update.message.reply_text(reply)


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

    app = ApplicationBuilder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("panic", panic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()
