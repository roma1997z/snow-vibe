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


def _value_from_row(row: Any, key: str, index: int) -> Any:
    if isinstance(row, sqlite3.Row):
        return row[key]
    return row[index]
