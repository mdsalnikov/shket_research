import logging
import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TG_BOT_KEY = os.getenv("TG_BOT_KEY", "")
DEFAULT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-oss-120b")
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "agent.log")


def setup_logging() -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
