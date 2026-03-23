from __future__ import annotations

import json
import secrets
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from snow_vibe.config import get_admin_password, get_admin_username
from snow_vibe.storage import Database


def setup_admin(app: FastAPI) -> None:
    @app.get("/admin", response_class=HTMLResponse)
    async def admin_home(request: Request) -> HTMLResponse:
        if not _is_authenticated(request):
            return RedirectResponse("/admin/login", status_code=303)

        database = Database()
        forecast_count = len(database.list_forecasts())
        state_count = len(database.list_state())
        return HTMLResponse(
            _page(
                "snow-vibe admin",
                f"""
                <p><strong>Backend:</strong> {escape(database.backend)}</p>
                <p><strong>Forecast rows:</strong> {forecast_count}</p>
                <p><strong>App state rows:</strong> {state_count}</p>
                <p>
                    <a href="/admin/forecasts">Forecast cache</a><br>
                    <a href="/admin/app-state">App state</a>
                </p>
                <form method="post" action="/admin/logout">
                    <button type="submit">Log out</button>
                </form>
                """,
            )
        )

    @app.get("/admin/login", response_class=HTMLResponse)
    async def admin_login_page(request: Request) -> HTMLResponse:
        if _is_authenticated(request):
            return RedirectResponse("/admin", status_code=303)
        return HTMLResponse(
            _page(
                "Admin Login",
                """
                <form method="post" action="/admin/login">
                    <label>Username<br><input type="text" name="username"></label><br><br>
                    <label>Password<br><input type="password" name="password"></label><br><br>
                    <button type="submit">Log in</button>
                </form>
                """,
            )
        )

    @app.post("/admin/login", response_class=HTMLResponse)
    async def admin_login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ) -> HTMLResponse:
        expected_username = get_admin_username()
        expected_password = get_admin_password()
        is_valid = bool(expected_password) and secrets.compare_digest(
            username, expected_username
        ) and secrets.compare_digest(password, expected_password)
        if is_valid:
            request.session["admin_authenticated"] = True
            return RedirectResponse("/admin", status_code=303)
        return HTMLResponse(
            _page(
                "Admin Login",
                """
                <p style="color:#b00020;"><strong>Invalid credentials</strong></p>
                <form method="post" action="/admin/login">
                    <label>Username<br><input type="text" name="username"></label><br><br>
                    <label>Password<br><input type="password" name="password"></label><br><br>
                    <button type="submit">Log in</button>
                </form>
                """,
            ),
            status_code=401,
        )

    @app.post("/admin/logout")
    async def admin_logout(request: Request) -> RedirectResponse:
        request.session.clear()
        return RedirectResponse("/admin/login", status_code=303)

    @app.get("/admin/app-state", response_class=HTMLResponse)
    async def admin_app_state(request: Request) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = Database()
        rows = database.list_state()
        rows_html = "".join(
            f"""
            <tr>
                <td><a href="/admin/app-state/{escape(row['key'])}">{escape(row['key'])}</a></td>
                <td><pre>{escape(_truncate(row['value'], 180))}</pre></td>
            </tr>
            """
            for row in rows
        )
        return HTMLResponse(
            _page(
                "App State",
                f"""
                <p><a href="/admin">Back</a></p>
                <table>
                    <thead><tr><th>Key</th><th>Value</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                """,
            )
        )

    @app.get("/admin/app-state/{key:path}", response_class=HTMLResponse)
    async def admin_app_state_edit(request: Request, key: str) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = Database()
        value = database.get_state(key)
        if value is None:
            return HTMLResponse(_page("Not Found", "<p>Key not found.</p>"), status_code=404)
        return HTMLResponse(
            _page(
                f"App State: {escape(key)}",
                f"""
                <p><a href="/admin/app-state">Back</a></p>
                <form method="post" action="/admin/app-state/{escape(key)}">
                    <p><strong>Key:</strong> {escape(key)}</p>
                    <label>Value<br>
                        <textarea name="value" rows="16" style="width:100%;font-family:monospace;">{escape(value)}</textarea>
                    </label><br><br>
                    <button type="submit">Save</button>
                </form>
                """,
            )
        )

    @app.post("/admin/app-state/{key:path}")
    async def admin_app_state_update(
        request: Request,
        key: str,
        value: str = Form(...),
    ):
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = Database()
        database.set_state(key, value)
        return RedirectResponse(f"/admin/app-state/{key}", status_code=303)

    @app.get("/admin/forecasts", response_class=HTMLResponse)
    async def admin_forecasts(request: Request) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = Database()
        rows = database.list_forecasts()
        rows_html = "".join(
            f"""
            <tr>
                <td><a href="/admin/forecasts/{escape(row['resort_slug'])}/{escape(row['cache_date'])}">{escape(row['resort_slug'])}</a></td>
                <td>{escape(row['cache_date'])}</td>
                <td>{escape(row['fetched_at'])}</td>
                <td>{escape(row['provider'])}</td>
            </tr>
            """
            for row in rows
        )
        return HTMLResponse(
            _page(
                "Forecast Cache",
                f"""
                <p><a href="/admin">Back</a></p>
                <table>
                    <thead><tr><th>Resort</th><th>Cache Date</th><th>Fetched At</th><th>Provider</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                """,
            )
        )

    @app.get("/admin/forecasts/{resort_slug}/{cache_date}", response_class=HTMLResponse)
    async def admin_forecast_edit(
        request: Request,
        resort_slug: str,
        cache_date: str,
    ) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = Database()
        row = database.get_forecast_row(resort_slug, cache_date)
        if row is None:
            return HTMLResponse(_page("Not Found", "<p>Forecast row not found.</p>"), status_code=404)
        return HTMLResponse(
            _page(
                f"Forecast: {escape(resort_slug)} {escape(cache_date)}",
                f"""
                <p><a href="/admin/forecasts">Back</a></p>
                <form method="post" action="/admin/forecasts/{escape(resort_slug)}/{escape(cache_date)}">
                    <label>Fetched At<br>
                        <input type="text" name="fetched_at" value="{escape(row['fetched_at'])}" style="width:100%;">
                    </label><br><br>
                    <label>Provider<br>
                        <input type="text" name="provider" value="{escape(row['provider'])}" style="width:100%;">
                    </label><br><br>
                    <label>Payload JSON<br>
                        <textarea name="payload_json" rows="28" style="width:100%;font-family:monospace;">{escape(row['payload_json'])}</textarea>
                    </label><br><br>
                    <button type="submit">Save</button>
                </form>
                """,
            )
        )

    @app.post("/admin/forecasts/{resort_slug}/{cache_date}")
    async def admin_forecast_update(
        request: Request,
        resort_slug: str,
        cache_date: str,
        fetched_at: str = Form(...),
        provider: str = Form(...),
        payload_json: str = Form(...),
    ):
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = Database()
        try:
            json.loads(payload_json)
        except json.JSONDecodeError as exc:
            return HTMLResponse(
                _page(
                    "Invalid JSON",
                    f"""
                    <p style="color:#b00020;"><strong>JSON error:</strong> {escape(str(exc))}</p>
                    <p><a href="/admin/forecasts/{escape(resort_slug)}/{escape(cache_date)}">Back</a></p>
                    """,
                ),
                status_code=400,
            )
        database.update_forecast_row(
            resort_slug=resort_slug,
            cache_date=cache_date,
            fetched_at=fetched_at,
            provider=provider,
            payload_json=payload_json,
        )
        return RedirectResponse(f"/admin/forecasts/{resort_slug}/{cache_date}", status_code=303)


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin_authenticated"))


def _require_auth(request: Request) -> RedirectResponse | None:
    if _is_authenticated(request):
        return None
    return RedirectResponse("/admin/login", status_code=303)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 16px; color: #111; }}
    a {{ color: #0b57d0; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #ddd; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
    input, textarea, button {{ font: inherit; }}
    button {{ padding: 8px 14px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  {body}
</body>
</html>"""
