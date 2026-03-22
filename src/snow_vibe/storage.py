from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from snow_vibe.config import get_database_path


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
        self.db_path = db_path or get_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
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
        return json.loads(row["payload_json"])

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

    def get_state(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = ?",
                (key,),
            ).fetchone()
        return None if row is None else row["value"]

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
