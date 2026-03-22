from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path


DEFAULT_USER_AGENT = "snow-vibe/0.1 (+https://github.com/rvzakharov/snow-vibe)"
DEFAULT_DB_PATH = "data/snow_vibe.db"
DEFAULT_ADMIN_USERNAME = "admin"


@lru_cache(maxsize=1)
def load_dotenv() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_user_agent() -> str:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_USER_AGENT", DEFAULT_USER_AGENT)


def get_database_path() -> Path:
    load_dotenv()
    return Path(os.environ.get("SNOW_VIBE_DB_PATH", DEFAULT_DB_PATH))


def get_telegram_bot_token() -> str | None:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_TELEGRAM_BOT_TOKEN")


def get_admin_username() -> str:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)


def get_admin_password() -> str | None:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_ADMIN_PASSWORD")


def get_admin_session_secret() -> str:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_ADMIN_SESSION_SECRET", secrets.token_urlsafe(32))


def get_telegram_webhook_secret() -> str | None:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_TELEGRAM_WEBHOOK_SECRET")
