import logging
import os

from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# API Keys
# ============================================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TG_BOT_KEY = os.getenv("TG_BOT_KEY", "")

# ============================================================================
# Provider Configuration
# ============================================================================
# Default provider: 'vllm' (local) or 'openrouter' (cloud)
PROVIDER_DEFAULT = os.getenv("PROVIDER_DEFAULT", "vllm")

# vLLM (local) configuration
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "Qwen/Qwen3.5-27B")
# vLLM typically doesn't need an API key, but allow one for auth setups
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "not-needed")

# OpenRouter (cloud) configuration
OPENROUTER_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME", "openai/gpt-oss-120b")

# Legacy support - maps to appropriate model based on provider
DEFAULT_MODEL = os.getenv("AGENT_MODEL", VLLM_MODEL_NAME)

# ============================================================================
# Agent Configuration
# ============================================================================
# Max retries when task fails; agent tries to self-heal before giving up
MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "10"))
# Project root: directory containing agent/ package (works from any cwd)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "agent.log")
BOT_ERRORS_LOG = os.path.join(PROJECT_ROOT, "logs", "bot_errors.log")

# Whitelist for TG bot - comma-separated usernames (without @)
# Example: TG_WHITELIST=mdsalnikov,user2,user3
# If empty or not set, all users are allowed (for development)
TG_WHITELIST_STR = os.getenv("TG_WHITELIST", "")


def _parse_whitelist(whitelist_str: str) -> set[str]:
    """Parse comma-separated whitelist into set of lowercase usernames."""
    if not whitelist_str:
        return set()  # Empty = allow all (development mode)
    return {name.strip().lower() for name in whitelist_str.split(",") if name.strip()}


TG_WHITELIST = _parse_whitelist(TG_WHITELIST_STR)


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
    os.makedirs(os.path.dirname(BOT_ERRORS_LOG), exist_ok=True)
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
