import logging
import os

from dotenv import load_dotenv

load_dotenv()

# VLLM configuration (local inference, priority over OpenRouter)
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "")
USE_VLLM = os.getenv("USE_VLLM", "false").lower() in ("true", "1", "yes")
VLLM_MODEL = os.getenv("VLLM_MODEL", "")  # Model for VLLM (required if USE_VLLM=true)

# OpenRouter configuration (cloud inference fallback)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")  # Model for OpenRouter

# Telegram bot
TG_BOT_KEY = os.getenv("TG_BOT_KEY", "")

# Legacy: AGENT_MODEL (for backward compatibility)
# If VLLM_MODEL or OPENROUTER_MODEL not set, fall back to AGENT_MODEL
AGENT_MODEL_LEGACY = os.getenv("AGENT_MODEL", "")


def get_model_name() -> str:
    """Get model name based on configuration.
    
    Priority:
    1. VLLM_MODEL if USE_VLLM=true and VLLM_MODEL is set
    2. OPENROUTER_MODEL if USE_VLLM=false and OPENROUTER_MODEL is set
    3. AGENT_MODEL (legacy) if set
    4. Default: openai/gpt-oss-120b for VLLM, z-ai/glm-5 for OpenRouter
    
    Returns:
        Model name to use
        
    """
    if USE_VLLM:
        # VLLM mode
        if VLLM_MODEL:
            return VLLM_MODEL
        if AGENT_MODEL_LEGACY:
            return AGENT_MODEL_LEGACY
        return "openai/gpt-oss-120b"  # Default for VLLM
    else:
        # OpenRouter mode
        if OPENROUTER_MODEL:
            return OPENROUTER_MODEL
        if AGENT_MODEL_LEGACY:
            return AGENT_MODEL_LEGACY
        return "z-ai/glm-5"  # Default for OpenRouter


DEFAULT_MODEL = get_model_name()

# Max retries when task fails; agent tries to self-heal before giving up
MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "10"))

# Project root: directory containing agent/ package (works from any cwd)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "agent.log")

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
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
