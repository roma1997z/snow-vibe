from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Query, Request
from starlette.middleware.sessions import SessionMiddleware

from snow_vibe.admin import setup_admin
from snow_vibe.bot import TelegramBot
from snow_vibe.config import get_admin_session_secret, get_telegram_webhook_secret
from snow_vibe.services import ForecastService


app = FastAPI(title="snow-vibe", version="0.1.0")
app.add_middleware(SessionMiddleware, secret_key=get_admin_session_secret())
service = ForecastService()
admin = setup_admin(app)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/resorts")
def list_resorts() -> list[dict]:
    return service.list_resorts()


@app.get("/resorts/{resort_slug}/forecast")
def get_forecast(
    resort_slug: str,
    force: bool = Query(default=False),
) -> dict:
    try:
        return service.get_forecast(resort_slug, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/resorts/{resort_slug}/refresh")
def refresh_forecast(resort_slug: str) -> dict:
    try:
        return service.get_forecast(resort_slug, force=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/refresh-all")
def refresh_all() -> dict:
    return {"items": service.refresh_all()}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    expected_secret = get_telegram_webhook_secret()
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    payload = await request.json()
    TelegramBot().process_update(payload)
    return {"ok": True}
