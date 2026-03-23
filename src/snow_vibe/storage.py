from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from snow_vibe.config import (
    get_database_path,
    get_turso_auth_token,
    get_turso_database_url,
    use_turso_database,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS resort_forecasts (
    resort_slug TEXT NOT NULL,
    cache_date TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (resort_slug, cache_date)
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_users (
    telegram_user_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    current_state TEXT NOT NULL,
    state_payload_json TEXT NOT NULL,
    last_action TEXT,
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_value TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_favorite_resorts (
    telegram_user_id TEXT NOT NULL,
    resort_slug TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (telegram_user_id, resort_slug)
);

CREATE TABLE IF NOT EXISTS user_trip_preferences (
    telegram_user_id TEXT PRIMARY KEY,
    start_date TEXT,
    end_date TEXT,
    notifications_enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.backend = "turso" if use_turso_database() else "sqlite"
        self.db_path = db_path or get_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.backend == "turso":
            import libsql

            connection = libsql.connect(
                str(self.db_path),
                sync_url=get_turso_database_url(),
                auth_token=get_turso_auth_token(),
            )
            connection.sync()
        else:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
            if self.backend == "turso":
                connection.sync()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def get_cached_forecast(self, resort_slug: str, cache_date: date) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM resort_forecasts
                WHERE resort_slug = ? AND cache_date = ?
                """,
                (resort_slug, cache_date.isoformat()),
            ).fetchone()
        if not row:
            return None
        return json.loads(_value_from_row(row, "payload_json", 0))

    def list_forecasts(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT resort_slug, cache_date, fetched_at, provider, payload_json
                FROM resort_forecasts
                ORDER BY cache_date DESC, resort_slug ASC
                """
            ).fetchall()
        return [
            {
                "resort_slug": _value_from_row(row, "resort_slug", 0),
                "cache_date": _value_from_row(row, "cache_date", 1),
                "fetched_at": _value_from_row(row, "fetched_at", 2),
                "provider": _value_from_row(row, "provider", 3),
                "payload_json": _value_from_row(row, "payload_json", 4),
            }
            for row in rows
        ]

    def get_forecast_row(self, resort_slug: str, cache_date: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT resort_slug, cache_date, fetched_at, provider, payload_json
                FROM resort_forecasts
                WHERE resort_slug = ? AND cache_date = ?
                """,
                (resort_slug, cache_date),
            ).fetchone()
        if row is None:
            return None
        return {
            "resort_slug": _value_from_row(row, "resort_slug", 0),
            "cache_date": _value_from_row(row, "cache_date", 1),
            "fetched_at": _value_from_row(row, "fetched_at", 2),
            "provider": _value_from_row(row, "provider", 3),
            "payload_json": _value_from_row(row, "payload_json", 4),
        }

    def save_forecast(
        self,
        *,
        resort_slug: str,
        cache_date: date,
        provider: str,
        payload: dict,
        fetched_at: datetime,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO resort_forecasts (
                    resort_slug, cache_date, fetched_at, provider, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(resort_slug, cache_date)
                DO UPDATE SET
                    fetched_at = excluded.fetched_at,
                    provider = excluded.provider,
                    payload_json = excluded.payload_json
                """,
                (
                    resort_slug,
                    cache_date.isoformat(),
                    fetched_at.isoformat(),
                    provider,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def update_forecast_row(
        self,
        *,
        resort_slug: str,
        cache_date: str,
        fetched_at: str,
        provider: str,
        payload_json: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE resort_forecasts
                SET fetched_at = ?, provider = ?, payload_json = ?
                WHERE resort_slug = ? AND cache_date = ?
                """,
                (fetched_at, provider, payload_json, resort_slug, cache_date),
            )

    def get_state(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = ?",
                (key,),
            ).fetchone()
        return None if row is None else _value_from_row(row, "value", 0)

    def list_state(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT key, value
                FROM app_state
                ORDER BY key ASC
                """
            ).fetchall()
        return [
            {
                "key": _value_from_row(row, "key", 0),
                "value": _value_from_row(row, "value", 1),
            }
            for row in rows
        ]

    def set_state(self, key: str, value: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key)
                DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def upsert_telegram_user(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        current_state: str,
        state_payload: dict | None,
        last_action: str | None,
        last_seen_at: str,
    ) -> None:
        payload_json = json.dumps(state_payload or {}, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_users (
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    current_state,
                    state_payload_json,
                    last_action,
                    last_seen_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id)
                DO UPDATE SET
                    chat_id = excluded.chat_id,
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    current_state = excluded.current_state,
                    state_payload_json = excluded.state_payload_json,
                    last_action = excluded.last_action,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    current_state,
                    payload_json,
                    last_action,
                    last_seen_at,
                    last_seen_at,
                ),
            )

    def log_user_action(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        action_type: str,
        action_value: str | None,
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_actions (
                    telegram_user_id,
                    chat_id,
                    action_type,
                    action_value,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_user_id, chat_id, action_type, action_value, created_at),
            )

    def record_user_state(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        current_state: str,
        state_payload: dict | None,
        action_type: str,
        action_value: str | None,
        created_at: str,
        log_action: bool = False,
    ) -> None:
        payload_json = json.dumps(state_payload or {}, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_users (
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    current_state,
                    state_payload_json,
                    last_action,
                    last_seen_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id)
                DO UPDATE SET
                    chat_id = excluded.chat_id,
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    current_state = excluded.current_state,
                    state_payload_json = excluded.state_payload_json,
                    last_action = excluded.last_action,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    current_state,
                    payload_json,
                    action_type,
                    created_at,
                    created_at,
                ),
            )
            if log_action:
                connection.execute(
                    """
                    INSERT INTO user_actions (
                        telegram_user_id,
                        chat_id,
                        action_type,
                        action_value,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (telegram_user_id, chat_id, action_type, action_value, created_at),
                )

    def list_telegram_users(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.telegram_user_id,
                    u.chat_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.current_state,
                    u.state_payload_json,
                    u.last_action,
                    u.last_seen_at,
                    u.created_at,
                    COUNT(a.id) AS action_count,
                    SUM(CASE WHEN a.action_type = 'choose_best_resort' THEN 1 ELSE 0 END) AS best_resort_count
                FROM telegram_users u
                LEFT JOIN user_actions a ON a.telegram_user_id = u.telegram_user_id
                GROUP BY
                    u.telegram_user_id,
                    u.chat_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.current_state,
                    u.state_payload_json,
                    u.last_action,
                    u.last_seen_at,
                    u.created_at
                ORDER BY u.last_seen_at DESC
                """
            ).fetchall()
        return [
            {
                "telegram_user_id": _value_from_row(row, "telegram_user_id", 0),
                "chat_id": _value_from_row(row, "chat_id", 1),
                "username": _value_from_row(row, "username", 2),
                "first_name": _value_from_row(row, "first_name", 3),
                "last_name": _value_from_row(row, "last_name", 4),
                "current_state": _value_from_row(row, "current_state", 5),
                "state_payload_json": _value_from_row(row, "state_payload_json", 6),
                "last_action": _value_from_row(row, "last_action", 7),
                "last_seen_at": _value_from_row(row, "last_seen_at", 8),
                "created_at": _value_from_row(row, "created_at", 9),
                "action_count": _value_from_row(row, "action_count", 10) or 0,
                "best_resort_count": _value_from_row(row, "best_resort_count", 11) or 0,
            }
            for row in rows
        ]

    def get_telegram_user(self, telegram_user_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    current_state,
                    state_payload_json,
                    last_action,
                    last_seen_at,
                    created_at
                FROM telegram_users
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "telegram_user_id": _value_from_row(row, "telegram_user_id", 0),
            "chat_id": _value_from_row(row, "chat_id", 1),
            "username": _value_from_row(row, "username", 2),
            "first_name": _value_from_row(row, "first_name", 3),
            "last_name": _value_from_row(row, "last_name", 4),
            "current_state": _value_from_row(row, "current_state", 5),
            "state_payload_json": _value_from_row(row, "state_payload_json", 6),
            "last_action": _value_from_row(row, "last_action", 7),
            "last_seen_at": _value_from_row(row, "last_seen_at", 8),
            "created_at": _value_from_row(row, "created_at", 9),
        }

    def get_user_context(self, telegram_user_id: str) -> dict:
        with self.connect() as connection:
            user_row = connection.execute(
                """
                SELECT
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    current_state,
                    state_payload_json,
                    last_action,
                    last_seen_at,
                    created_at
                FROM telegram_users
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            ).fetchone()
            favorite_rows = connection.execute(
                """
                SELECT resort_slug
                FROM user_favorite_resorts
                WHERE telegram_user_id = ?
                ORDER BY created_at ASC, resort_slug ASC
                """,
                (telegram_user_id,),
            ).fetchall()
            preference_row = connection.execute(
                """
                SELECT telegram_user_id, start_date, end_date, notifications_enabled, updated_at
                FROM user_trip_preferences
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            ).fetchone()

        user = None
        if user_row is not None:
            user = {
                "telegram_user_id": _value_from_row(user_row, "telegram_user_id", 0),
                "chat_id": _value_from_row(user_row, "chat_id", 1),
                "username": _value_from_row(user_row, "username", 2),
                "first_name": _value_from_row(user_row, "first_name", 3),
                "last_name": _value_from_row(user_row, "last_name", 4),
                "current_state": _value_from_row(user_row, "current_state", 5),
                "state_payload_json": _value_from_row(user_row, "state_payload_json", 6),
                "last_action": _value_from_row(user_row, "last_action", 7),
                "last_seen_at": _value_from_row(user_row, "last_seen_at", 8),
                "created_at": _value_from_row(user_row, "created_at", 9),
            }

        favorites = [_value_from_row(row, "resort_slug", 0) for row in favorite_rows]
        if preference_row is None:
            trip_preferences = {
                "telegram_user_id": telegram_user_id,
                "start_date": None,
                "end_date": None,
                "notifications_enabled": False,
                "updated_at": None,
            }
        else:
            trip_preferences = {
                "telegram_user_id": _value_from_row(preference_row, "telegram_user_id", 0),
                "start_date": _value_from_row(preference_row, "start_date", 1),
                "end_date": _value_from_row(preference_row, "end_date", 2),
                "notifications_enabled": bool(_value_from_row(preference_row, "notifications_enabled", 3)),
                "updated_at": _value_from_row(preference_row, "updated_at", 4),
            }

        return {
            "user": user,
            "favorites": favorites,
            "trip_preferences": trip_preferences,
        }

    def list_user_actions(
        self,
        *,
        telegram_user_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        query = """
            SELECT id, telegram_user_id, chat_id, action_type, action_value, created_at
            FROM user_actions
        """
        params: tuple[Any, ...]
        if telegram_user_id is not None:
            query += " WHERE telegram_user_id = ?"
            params = (telegram_user_id, limit)
        else:
            params = (limit,)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "id": _value_from_row(row, "id", 0),
                "telegram_user_id": _value_from_row(row, "telegram_user_id", 1),
                "chat_id": _value_from_row(row, "chat_id", 2),
                "action_type": _value_from_row(row, "action_type", 3),
                "action_value": _value_from_row(row, "action_value", 4),
                "created_at": _value_from_row(row, "created_at", 5),
            }
            for row in rows
        ]

    def list_user_favorite_resorts(self, telegram_user_id: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT resort_slug
                FROM user_favorite_resorts
                WHERE telegram_user_id = ?
                ORDER BY created_at ASC, resort_slug ASC
                """,
                (telegram_user_id,),
            ).fetchall()
        return [_value_from_row(row, "resort_slug", 0) for row in rows]

    def toggle_user_favorite_resort(
        self,
        *,
        telegram_user_id: str,
        resort_slug: str,
        created_at: str,
    ) -> tuple[bool, list[str]]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM user_favorite_resorts
                WHERE telegram_user_id = ? AND resort_slug = ?
                """,
                (telegram_user_id, resort_slug),
            ).fetchone()
            if row is not None:
                connection.execute(
                    """
                    DELETE FROM user_favorite_resorts
                    WHERE telegram_user_id = ? AND resort_slug = ?
                    """,
                    (telegram_user_id, resort_slug),
                )
                added = False
            else:
                connection.execute(
                    """
                    INSERT INTO user_favorite_resorts (
                        telegram_user_id,
                        resort_slug,
                        created_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(telegram_user_id, resort_slug)
                    DO NOTHING
                    """,
                    (telegram_user_id, resort_slug, created_at),
                )
                added = True
            rows = connection.execute(
                """
                SELECT resort_slug
                FROM user_favorite_resorts
                WHERE telegram_user_id = ?
                ORDER BY created_at ASC, resort_slug ASC
                """,
                (telegram_user_id,),
            ).fetchall()
        favorites = [_value_from_row(row, "resort_slug", 0) for row in rows]
        return added, favorites

    def get_user_trip_preferences(self, telegram_user_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT telegram_user_id, start_date, end_date, notifications_enabled, updated_at
                FROM user_trip_preferences
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            ).fetchone()
        if row is None:
            return {
                "telegram_user_id": telegram_user_id,
                "start_date": None,
                "end_date": None,
                "notifications_enabled": False,
                "updated_at": None,
            }
        return {
            "telegram_user_id": _value_from_row(row, "telegram_user_id", 0),
            "start_date": _value_from_row(row, "start_date", 1),
            "end_date": _value_from_row(row, "end_date", 2),
            "notifications_enabled": bool(_value_from_row(row, "notifications_enabled", 3)),
            "updated_at": _value_from_row(row, "updated_at", 4),
        }

    def save_user_trip_preferences(
        self,
        *,
        telegram_user_id: str,
        start_date: str | None,
        end_date: str | None,
        notifications_enabled: bool,
        updated_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_trip_preferences (
                    telegram_user_id,
                    start_date,
                    end_date,
                    notifications_enabled,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id)
                DO UPDATE SET
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    notifications_enabled = excluded.notifications_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    telegram_user_id,
                    start_date,
                    end_date,
                    int(notifications_enabled),
                    updated_at,
                ),
            )

    def set_user_notifications_enabled(
        self,
        *,
        telegram_user_id: str,
        notifications_enabled: bool,
        updated_at: str,
    ) -> None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT start_date, end_date
                FROM user_trip_preferences
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            ).fetchone()
            start_date = None if row is None else _value_from_row(row, "start_date", 0)
            end_date = None if row is None else _value_from_row(row, "end_date", 1)
            connection.execute(
                """
                INSERT INTO user_trip_preferences (
                    telegram_user_id,
                    start_date,
                    end_date,
                    notifications_enabled,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id)
                DO UPDATE SET
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    notifications_enabled = excluded.notifications_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    telegram_user_id,
                    start_date,
                    end_date,
                    int(notifications_enabled),
                    updated_at,
                ),
            )

    def clear_user_trip_dates(self, *, telegram_user_id: str, updated_at: str) -> None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT notifications_enabled
                FROM user_trip_preferences
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            ).fetchone()
            notifications_enabled = (
                False if row is None else bool(_value_from_row(row, "notifications_enabled", 0))
            )
            connection.execute(
                """
                INSERT INTO user_trip_preferences (
                    telegram_user_id,
                    start_date,
                    end_date,
                    notifications_enabled,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id)
                DO UPDATE SET
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    notifications_enabled = excluded.notifications_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    telegram_user_id,
                    None,
                    None,
                    int(notifications_enabled),
                    updated_at,
                ),
            )

    def list_users_with_notifications_enabled(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.telegram_user_id,
                    u.chat_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    p.start_date,
                    p.end_date,
                    p.notifications_enabled,
                    p.updated_at
                FROM telegram_users u
                JOIN user_trip_preferences p
                  ON p.telegram_user_id = u.telegram_user_id
                WHERE p.notifications_enabled = 1
                ORDER BY p.updated_at ASC, u.last_seen_at DESC
                """
            ).fetchall()
        return [
            {
                "telegram_user_id": _value_from_row(row, "telegram_user_id", 0),
                "chat_id": _value_from_row(row, "chat_id", 1),
                "username": _value_from_row(row, "username", 2),
                "first_name": _value_from_row(row, "first_name", 3),
                "last_name": _value_from_row(row, "last_name", 4),
                "start_date": _value_from_row(row, "start_date", 5),
                "end_date": _value_from_row(row, "end_date", 6),
                "notifications_enabled": bool(_value_from_row(row, "notifications_enabled", 7)),
                "updated_at": _value_from_row(row, "updated_at", 8),
            }
            for row in rows
        ]


def _value_from_row(row: Any, key: str, index: int) -> Any:
    if isinstance(row, sqlite3.Row):
        return row[key]
    return row[index]
