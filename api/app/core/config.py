"""Runtime settings, read from environment / api/.env. Secrets are never returned by the API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = API_DIR.parent
load_dotenv(API_DIR / ".env")

DEMO_DIR = ROOT_DIR / "demo_data"
DB_PATH = Path(os.getenv("OPS_DB_PATH", API_DIR / "ops.db"))

# Claude. The SDK also resolves ANTHROPIC_AUTH_TOKEN / `ant auth login` profiles.
AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-opus-5-5")
BULK_MODEL = os.getenv("BULK_MODEL", "claude-haiku-5-5")

# Hybrid AI router: other model providers (optional)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
PRIVATE_LLM_BASE_URL = os.getenv("PRIVATE_LLM_BASE_URL", "http://localhost:11434/v1")  # Ollama / vLLM / any OpenAI-compatible server
PRIVATE_LLM_MODEL = os.getenv("PRIVATE_LLM_MODEL", "qwen2.5:7b")
PRIVATE_LLM_API_KEY = os.getenv("PRIVATE_LLM_API_KEY", "local")

# Optional live Salesforce org (REST API). Either an access token + instance URL,
# or the OAuth username-password flow with a connected app.
SF_INSTANCE_URL = os.getenv("SF_INSTANCE_URL", "")
SF_ACCESS_TOKEN = os.getenv("SF_ACCESS_TOKEN", "")
SF_LOGIN_URL = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")
SF_CLIENT_ID = os.getenv("SF_CLIENT_ID", "")
SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET", "")
SF_USERNAME = os.getenv("SF_USERNAME", "")
SF_PASSWORD = os.getenv("SF_PASSWORD", "")  # password + security token
SF_API_VERSION = os.getenv("SF_API_VERSION", "v62.0")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


def claude_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def salesforce_configured() -> bool:
    return bool((SF_INSTANCE_URL and SF_ACCESS_TOKEN) or (SF_CLIENT_ID and SF_USERNAME and SF_PASSWORD))
