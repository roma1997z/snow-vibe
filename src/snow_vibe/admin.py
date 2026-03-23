from __future__ import annotations

import json
import secrets
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from snow_vibe.config import get_admin_password, get_admin_username
from snow_vibe.storage import Database, get_database


def setup_admin(app: FastAPI) -> None:
    @app.get("/admin", response_class=HTMLResponse)
    async def admin_home(request: Request) -> HTMLResponse:
        if not _is_authenticated(request):
            return RedirectResponse("/admin/login", status_code=303)

        database = get_database()
        forecast_count = len(database.list_forecasts())
        state_count = len(database.list_state())
        users = database.list_telegram_users()
        user_count = len(users)
        action_count = len(database.list_user_actions(limit=1000))
        favorite_count = sum(
            len(database.list_user_favorite_resorts(row["telegram_user_id"]))
            for row in users
        )
        return HTMLResponse(
            _page(
                "snow-vibe admin",
                f"""
                <p><strong>Backend:</strong> {escape(database.backend)}</p>
                <p><strong>Forecast rows:</strong> {forecast_count}</p>
                <p><strong>App state rows:</strong> {state_count}</p>
                <p><strong>Telegram users:</strong> {user_count}</p>
                <p><strong>User actions:</strong> {action_count}</p>
                <p><strong>Favorite selections:</strong> {favorite_count}</p>
                <p>
                    <a href="/admin/forecasts">Forecast cache</a><br>
                    <a href="/admin/app-state">App state</a><br>
                    <a href="/admin/users">Telegram users</a><br>
                    <a href="/admin/actions">User actions</a>
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
        database = get_database()
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
        database = get_database()
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
        database = get_database()
        database.set_state(key, value)
        return RedirectResponse(f"/admin/app-state/{key}", status_code=303)

    @app.get("/admin/forecasts", response_class=HTMLResponse)
    async def admin_forecasts(request: Request) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = get_database()
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

    @app.get("/admin/users", response_class=HTMLResponse)
    async def admin_users(request: Request) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = get_database()
        rows = database.list_telegram_users()
        rows_html = "".join(
            f"""
            <tr>
                <td><a href="/admin/users/{escape(row['telegram_user_id'])}">{escape(row['telegram_user_id'])}</a></td>
                <td>{escape(_display_user_name(row))}</td>
                <td>{escape(row['current_state'])}</td>
                <td>{row['action_count']}</td>
                <td>{row['best_resort_count']}</td>
                <td>{escape(row['last_action'] or '-')}</td>
                <td>{escape(row['last_seen_at'])}</td>
            </tr>
            """
            for row in rows
        )
        return HTMLResponse(
            _page(
                "Telegram Users",
                f"""
                <p><a href="/admin">Back</a></p>
                <table>
                    <thead><tr><th>User ID</th><th>User</th><th>Current State</th><th>Actions</th><th>Best Clicks</th><th>Last Action</th><th>Last Seen</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                """,
            )
        )

    @app.get("/admin/users/{telegram_user_id}", response_class=HTMLResponse)
    async def admin_user_detail(request: Request, telegram_user_id: str) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = get_database()
        user = database.get_telegram_user(telegram_user_id)
        if user is None:
            return HTMLResponse(_page("Not Found", "<p>User not found.</p>"), status_code=404)
        actions = database.list_user_actions(telegram_user_id=telegram_user_id, limit=100)
        favorites = database.list_user_favorite_resorts(telegram_user_id)
        trip_preferences = database.get_user_trip_preferences(telegram_user_id)
        actions_html = "".join(
            f"""
            <tr>
                <td>{escape(action['created_at'])}</td>
                <td>{escape(action['action_type'])}</td>
                <td>{escape(action['action_value'] or '-')}</td>
            </tr>
            """
            for action in actions
        )
        return HTMLResponse(
            _page(
                f"User: {escape(telegram_user_id)}",
                f"""
                <p><a href="/admin/users">Back</a></p>
                <p><strong>User:</strong> {escape(_display_user_name(user))}</p>
                <p><strong>Chat ID:</strong> {escape(user['chat_id'])}</p>
                <p><strong>Current state:</strong> {escape(user['current_state'])}</p>
                <p><strong>Last action:</strong> {escape(user['last_action'] or '-')}</p>
                <p><strong>Last seen:</strong> {escape(user['last_seen_at'])}</p>
                <p><strong>Favorite resorts:</strong> {escape(', '.join(favorites) if favorites else '-')}</p>
                <p><strong>Trip dates:</strong> {escape(_format_trip_dates(trip_preferences))}</p>
                <p><strong>Notifications:</strong> {escape('enabled' if trip_preferences['notifications_enabled'] else 'disabled')}</p>
                <p><strong>State payload:</strong></p>
                <pre>{escape(user['state_payload_json'])}</pre>
                <h2>Recent actions</h2>
                <table>
                    <thead><tr><th>Created</th><th>Action</th><th>Value</th></tr></thead>
                    <tbody>{actions_html}</tbody>
                </table>
                """,
            )
        )

    @app.get("/admin/actions", response_class=HTMLResponse)
    async def admin_actions(request: Request) -> HTMLResponse:
        auth = _require_auth(request)
        if auth is not None:
            return auth
        database = get_database()
        rows = database.list_user_actions(limit=300)
        rows_html = "".join(
            f"""
            <tr>
                <td>{escape(action['created_at'])}</td>
                <td><a href="/admin/users/{escape(action['telegram_user_id'])}">{escape(action['telegram_user_id'])}</a></td>
                <td>{escape(action['action_type'])}</td>
                <td>{escape(action['action_value'] or '-')}</td>
            </tr>
            """
            for action in rows
        )
        return HTMLResponse(
            _page(
                "User Actions",
                f"""
                <p><a href="/admin">Back</a></p>
                <table>
                    <thead><tr><th>Created</th><th>User ID</th><th>Action</th><th>Value</th></tr></thead>
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
        database = get_database()
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
        database = get_database()
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


def _display_user_name(user: dict) -> str:
    if user.get("username"):
        return f"@{user['username']}"
    name = " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part)
    return name or user.get("telegram_user_id", "unknown")


def _format_trip_dates(preferences: dict) -> str:
    start_date = preferences.get("start_date")
    end_date = preferences.get("end_date")
    if not start_date or not end_date:
        return "-"
    return f"{start_date} -> {end_date}"


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
