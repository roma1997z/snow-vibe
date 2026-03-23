from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, Header, HTTPException, Query, Request
from starlette.middleware.sessions import SessionMiddleware

from snow_vibe.admin import setup_admin
from snow_vibe.bot import TelegramBot
from snow_vibe.config import (
    get_admin_session_secret,
    get_cron_secret,
    get_telegram_webhook_secret,
)
from snow_vibe.services import ForecastService


app = FastAPI(title="snow-vibe", version="0.1.0")
app.add_middleware(SessionMiddleware, secret_key=get_admin_session_secret())
setup_admin(app)


@lru_cache(maxsize=1)
def get_service() -> ForecastService:
    return ForecastService()


@lru_cache(maxsize=1)
def get_bot() -> TelegramBot:
    return TelegramBot(service=get_service())


@app.get("/")
def root() -> dict:
    return {"service": "snow-vibe", "status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/resorts")
def list_resorts() -> list[dict]:
    return get_service().list_resorts()


@app.get("/resorts/{resort_slug}/forecast")
def get_forecast(
    resort_slug: str,
    force: bool = Query(default=False),
) -> dict:
    try:
        return get_service().get_forecast(resort_slug, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/resorts/{resort_slug}/refresh")
def refresh_forecast(resort_slug: str) -> dict:
    try:
        return get_service().get_forecast(resort_slug, force=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/refresh-all")
def refresh_all() -> dict:
    return {"items": get_service().refresh_all()}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    expected_secret = get_telegram_webhook_secret()
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    payload = await request.json()
    get_bot().process_update(payload)
    return {"ok": True}


@app.get("/internal/notify-trip-watchers")
def notify_trip_watchers(
    authorization: str | None = Header(default=None),
) -> dict:
    expected_secret = get_cron_secret()
    if expected_secret and authorization != f"Bearer {expected_secret}":
        raise HTTPException(status_code=401, detail="Invalid cron authorization")

    items = get_bot().send_trip_notifications()
    return {
        "ok": True,
        "sent_count": len(items),
        "items": items,
    }
