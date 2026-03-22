from __future__ import annotations

import secrets

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from snow_vibe.config import (
    get_admin_password,
    get_admin_session_secret,
    get_admin_username,
)
from snow_vibe.orm import AppStateRow, ResortForecastRow, engine


class ResortForecastAdmin(ModelView, model=ResortForecastRow):
    name = "Forecast Cache"
    name_plural = "Forecast Cache"
    icon = "fa-solid fa-snowflake"

    column_list = [
        ResortForecastRow.resort_slug,
        ResortForecastRow.cache_date,
        ResortForecastRow.fetched_at,
        ResortForecastRow.provider,
    ]
    column_searchable_list = [
        ResortForecastRow.resort_slug,
        ResortForecastRow.provider,
        ResortForecastRow.payload_json,
    ]
    column_sortable_list = [
        ResortForecastRow.resort_slug,
        ResortForecastRow.cache_date,
        ResortForecastRow.fetched_at,
    ]
    can_create = False
    can_export = True
    can_view_details = True

    form_excluded_columns = []
    form_widget_args = {
        "payload_json": {
            "rows": 24,
            "style": "font-family: monospace;",
        }
    }


class AppStateAdmin(ModelView, model=AppStateRow):
    name = "App State"
    name_plural = "App State"
    icon = "fa-solid fa-gear"

    column_list = [AppStateRow.key, AppStateRow.value]
    column_searchable_list = [AppStateRow.key, AppStateRow.value]
    column_sortable_list = [AppStateRow.key]
    can_create = False
    can_export = True
    can_view_details = True

    form_widget_args = {
        "value": {
            "rows": 8,
            "style": "font-family: monospace;",
        }
    }


class AdminAuth(AuthenticationBackend):
    def __init__(self) -> None:
        super().__init__(secret_key=get_admin_session_secret())

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))

        expected_username = get_admin_username()
        expected_password = get_admin_password()
        if not expected_password:
            return False

        is_valid = secrets.compare_digest(username, expected_username) and secrets.compare_digest(
            password, expected_password
        )
        if is_valid:
            request.session.update({"admin_authenticated": True})
        return is_valid

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin_authenticated"))


def setup_admin(app) -> Admin:
    admin = Admin(
        app,
        engine,
        base_url="/admin",
        title="snow-vibe admin",
        authentication_backend=AdminAuth(),
    )
    admin.add_view(ResortForecastAdmin)
    admin.add_view(AppStateAdmin)
    return admin
