import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from agent.config import TG_BOT_KEY

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Shket Research Agent online. Send me a task.")


async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning("/panic invoked by %s", update.effective_user.id)
    await update.message.reply_text("PANIC: halting all agent processes.")
    os._exit(1)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    logger.info("Task from %s: %s", update.effective_user.id, text)
    reply = f"Agent received task: {text}\nAgent core not yet implemented — scaffold only."
    await update.message.reply_text(reply)


def run_bot() -> None:
    token = TG_BOT_KEY
    if not token or token.startswith("your_"):
        raise SystemExit("TG_BOT_KEY is not configured. Set it in .env or environment.")

    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panic", panic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()
