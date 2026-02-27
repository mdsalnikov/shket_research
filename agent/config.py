import logging
import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TG_BOT_KEY = os.getenv("TG_BOT_KEY", "")
DEFAULT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-oss-120b")
# Max retries when task fails; agent tries to self-heal before giving up
MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "3"))
# Project root: directory containing agent/ package (works from any cwd)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "agent.log")

# Read version from VERSION file
def _get_version() -> str:
    version_file = os.path.join(PROJECT_ROOT, "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"  # Fallback if VERSION file doesn't exist

VERSION = _get_version()


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
