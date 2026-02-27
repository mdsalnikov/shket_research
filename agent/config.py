import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TG_BOT_KEY = os.getenv("TG_BOT_KEY", "")

DEFAULT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-oss-120b")
