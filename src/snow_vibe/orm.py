from __future__ import annotations

from pathlib import Path

from sqlalchemy import PrimaryKeyConstraint, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from snow_vibe.config import get_database_path


class Base(DeclarativeBase):
    pass


def build_database_url(db_path: Path | None = None) -> str:
    path = (db_path or get_database_path()).resolve()
    return f"sqlite:///{path}"


engine = create_engine(
    build_database_url(),
    connect_args={"check_same_thread": False},
)


class ResortForecastRow(Base):
    __tablename__ = "resort_forecasts"
    __table_args__ = (
        PrimaryKeyConstraint("resort_slug", "cache_date"),
    )

    resort_slug: Mapped[str] = mapped_column(String, nullable=False)
    cache_date: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class AppStateRow(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
