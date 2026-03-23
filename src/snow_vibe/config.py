from __future__ import annotations

import os
import secrets
import tempfile
from functools import lru_cache
from pathlib import Path


DEFAULT_USER_AGENT = "snow-vibe/0.1 (+https://github.com/rvzakharov/snow-vibe)"
DEFAULT_DB_PATH = "data/snow_vibe.db"
DEFAULT_VERCEL_DB_PATH = "/tmp/snow_vibe.db"
DEFAULT_TURSO_REPLICA_PATH = "data/snow_vibe_turso.db"
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
        normalized = value.strip()
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {"'", '"'}
        ):
            normalized = normalized[1:-1]
        os.environ.setdefault(key.strip(), normalized)


def get_user_agent() -> str:
    load_dotenv()
    return os.environ.get("SNOW_VIBE_USER_AGENT", DEFAULT_USER_AGENT)


def get_database_path() -> Path:
    load_dotenv()
    configured_path = os.environ.get("SNOW_VIBE_DB_PATH")
    if configured_path:
        path = Path(configured_path)
        if os.environ.get("VERCEL") == "1" and not path.is_absolute():
            normalized = configured_path.lstrip("./")
            if normalized == "tmp" or normalized.startswith("tmp/"):
                return Path(tempfile.gettempdir()) / normalized.removeprefix("tmp/").removeprefix("tmp")
        return path
    if use_turso_database():
        if os.environ.get("VERCEL") == "1":
            return Path(tempfile.gettempdir()) / "snow_vibe_turso.db"
        return Path(DEFAULT_TURSO_REPLICA_PATH)
    if os.environ.get("VERCEL") == "1":
        return Path(tempfile.gettempdir()) / "snow_vibe.db"
    return Path(DEFAULT_DB_PATH)


def get_turso_database_url() -> str | None:
    load_dotenv()
    return os.environ.get("TURSO_DATABASE_URL")


def get_turso_auth_token() -> str | None:
    load_dotenv()
    return os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get(
        "TURSO_DATABASE_TURSO_AUTH_TOKEN"
    )


def use_turso_database() -> bool:
    return bool(get_turso_database_url() and get_turso_auth_token())


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
