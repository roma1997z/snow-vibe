from __future__ import annotations

import json
from datetime import UTC, date, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from snow_vibe.config import get_telegram_bot_token, get_telegram_webhook_secret
from snow_vibe.http import build_ssl_context
from snow_vibe.serialization import format_telegram_resort_forecast
from snow_vibe.services import ForecastService
from snow_vibe.storage import Database


SHOW_RESORTS_TEXT = "Показать курорты"
BEST_RESORT_TEXT = "Выбрать лучший курорт"
FAVORITES_TEXT = "Избранные курорты"
TRIP_PLAN_TEXT = "План поездки"

WELCOME_TEXT = (
    "<b>snow vibe</b>\n"
    "Выбери действие в меню ниже.\n\n"
    "Сейчас можно посмотреть доступные курорты, выбрать избранные, сохранить даты поездки и получить лучший вариант под себя."
)


class TelegramBot:
    def __init__(
        self,
        *,
        service: ForecastService | None = None,
        database: Database | None = None,
    ) -> None:
        token = get_telegram_bot_token()
        if not token:
            raise RuntimeError("SNOW_VIBE_TELEGRAM_BOT_TOKEN is not configured")

        self.token = token
        self.service = service or ForecastService()
        self.database = database or Database()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.resorts = self.service.list_resorts()
        self.resort_names = {resort["slug"]: resort["name"] for resort in self.resorts}

    def run_polling(self) -> None:
        while True:
            for update in self.get_updates():
                self.process_update(update)

    def get_updates(self, timeout: int = 30) -> list[dict]:
        offset = self.database.get_state("telegram.last_update_id")
        params = {"timeout": str(timeout)}
        if offset is not None:
            params["offset"] = str(int(offset) + 1)
        payload = self._request("getUpdates", params)
        return payload["result"]

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        params = {
            "chat_id": str(chat_id),
            "text": text,
        }
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_markup is not None:
            params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        self._request("sendMessage", params)

    def process_update(self, update: dict) -> None:
        self.database.set_state("telegram.last_update_id", str(update["update_id"]))

        callback_query = update.get("callback_query")
        if callback_query is not None:
            self._handle_callback_query(callback_query)
            return

        message = update.get("message")
        if not message or "text" not in message:
            return

        chat_id = message["chat"]["id"]
        text = message["text"].strip()
        from_user = message.get("from", {})
        user_context = self._get_user_context(from_user)
        current_user = user_context["user"]
        reserved_texts = {
            "/start",
            "/help",
            "/resorts",
            SHOW_RESORTS_TEXT,
            BEST_RESORT_TEXT,
            FAVORITES_TEXT,
            TRIP_PLAN_TEXT,
        }

        if (
            current_user
            and current_user["current_state"] == "awaiting_trip_dates"
            and text not in reserved_texts
            and not text.startswith("/weather")
            and not text.startswith("/refresh")
        ):
            if self._handle_trip_dates_input(chat_id, text, from_user=from_user):
                return

        if text == "/start" or text == "/help":
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="main_menu",
                state_payload={"entrypoint": text},
                action_type="open_start",
                action_value=text,
            )
            self.send_message(
                chat_id,
                WELCOME_TEXT,
                parse_mode="HTML",
                reply_markup=self._main_menu_markup(),
            )
            return

        if text == "/resorts" or text == SHOW_RESORTS_TEXT:
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="browsing_resorts",
                state_payload={},
                action_type="open_resorts",
                action_value=None,
            )
            self._send_resort_picker(chat_id)
            return

        if text.startswith("/weather"):
            _, _, slug = text.partition(" ")
            slug = slug.strip() or "bigwood"
            self._send_forecast(chat_id, slug, force=False, from_user=from_user, source="command")
            return

        if text.startswith("/refresh"):
            _, _, slug = text.partition(" ")
            slug = slug.strip() or "bigwood"
            self._send_forecast(chat_id, slug, force=True, from_user=from_user, source="refresh")
            return

        if text == BEST_RESORT_TEXT:
            self._send_best_resort(chat_id, from_user=from_user)
            return

        if text == FAVORITES_TEXT:
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="managing_favorites",
                state_payload={},
                action_type="open_favorites",
                action_value=None,
            )
            self._send_favorites_picker(chat_id, user_context=user_context)
            return

        if text == TRIP_PLAN_TEXT:
            self._send_trip_settings(chat_id, from_user=from_user, user_context=user_context)
            return

        self._track_user_state(
            from_user=from_user,
            chat_id=chat_id,
            current_state="main_menu",
            state_payload={"entrypoint": "fallback"},
            action_type="open_main_menu",
            action_value=text,
        )
        self.send_message(
            chat_id,
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
        )

    def set_webhook(self, url: str, *, drop_pending_updates: bool = True) -> dict:
        params = {
            "url": url,
            "drop_pending_updates": str(drop_pending_updates).lower(),
        }
        secret = get_telegram_webhook_secret()
        if secret:
            params["secret_token"] = secret
        return self._request("setWebhook", params)

    def get_webhook_info(self) -> dict:
        return self._request("getWebhookInfo", {})

    def delete_webhook(self, *, drop_pending_updates: bool = False) -> dict:
        return self._request(
            "deleteWebhook",
            {"drop_pending_updates": str(drop_pending_updates).lower()},
        )

    def _send_forecast(
        self,
        chat_id: int,
        slug: str,
        *,
        force: bool,
        from_user: dict | None = None,
        source: str = "manual",
    ) -> None:
        try:
            payload = self.service.get_forecast(slug, force=force)
        except KeyError:
            self.send_message(
                chat_id,
                f"Не знаю курорт '{slug}'. Выбери вариант из списка.",
                reply_markup=self._main_menu_markup(),
            )
            return
        if from_user is not None:
            action_type = "refresh_resort" if force else "view_resort"
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="viewing_resort",
                state_payload={"resort_slug": slug, "source": source},
                action_type=action_type,
                action_value=slug,
            )
        self.send_message(
            chat_id,
            format_telegram_resort_forecast(payload),
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
        )

    def _send_resort_picker(self, chat_id: int) -> None:
        keyboard = [
            [{"text": resort["name"], "callback_data": f'resort:{resort["slug"]}'}]
            for resort in self.resorts
        ]
        self.send_message(
            chat_id,
            "Выбери курорт:",
            reply_markup={"inline_keyboard": keyboard},
        )

    def _send_best_resort(self, chat_id: int, *, from_user: dict | None = None) -> None:
        user_context = self._get_user_context(from_user)
        favorite_slugs = user_context["favorites"]
        trip_preferences = user_context["trip_preferences"]
        start_date = self._parse_iso_date(trip_preferences.get("start_date"))
        end_date = self._parse_iso_date(trip_preferences.get("end_date"))
        result = self.service.get_best_resort(
            force=False,
            resort_slugs=favorite_slugs or None,
            start_date=start_date,
            end_date=end_date,
        )
        if result is None:
            self.send_message(
                chat_id,
                "На выбранные даты пока нет прогноза. Сохрани диапазон и включи уведомления, чтобы я использовал его позже.",
                reply_markup=self._main_menu_markup(),
            )
            return

        best_slug = result["slug"]
        if from_user is not None:
            reason = result["reasons"][0] if result["reasons"] else "лучшие условия по снегу и температуре"
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="viewing_best_resort",
                state_payload={
                    "resort_slug": best_slug,
                    "reason": reason,
                    "start_date": trip_preferences.get("start_date"),
                    "end_date": trip_preferences.get("end_date"),
                    "favorites_count": len(favorite_slugs),
                },
                action_type="choose_best_resort",
                action_value=best_slug,
            )
        self.send_message(
            chat_id,
            self._build_best_resort_message(
                result,
                favorite_slugs=favorite_slugs,
                start_date=start_date,
                end_date=end_date,
                title="Лучший курорт сейчас",
            ),
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
        )

    def send_trip_notifications(self) -> list[dict]:
        sent_notifications = []
        for user in self.database.list_users_with_notifications_enabled():
            start_date = self._parse_iso_date(user.get("start_date"))
            end_date = self._parse_iso_date(user.get("end_date"))
            user_context = self.database.get_user_context(user["telegram_user_id"])
            favorite_slugs = user_context["favorites"]
            if start_date is None or end_date is None or not favorite_slugs:
                continue

            result = self.service.get_best_resort(
                force=False,
                resort_slugs=favorite_slugs,
                start_date=start_date,
                end_date=end_date,
            )
            if result is None:
                continue

            chat_id = int(user["chat_id"])
            self.send_message(
                chat_id,
                self._build_best_resort_message(
                    result,
                    favorite_slugs=favorite_slugs,
                    start_date=start_date,
                    end_date=end_date,
                    title="Пора планировать поездку",
                ),
                parse_mode="HTML",
                reply_markup=self._main_menu_markup(),
            )
            self.database.set_user_notifications_enabled(
                telegram_user_id=user["telegram_user_id"],
                notifications_enabled=False,
                updated_at=self._now_iso(),
            )
            self.database.log_user_action(
                telegram_user_id=user["telegram_user_id"],
                chat_id=user["chat_id"],
                action_type="send_trip_notification",
                action_value=result["slug"],
                created_at=self._now_iso(),
            )
            sent_notifications.append(
                {
                    "telegram_user_id": user["telegram_user_id"],
                    "chat_id": user["chat_id"],
                    "resort_slug": result["slug"],
                }
            )
        return sent_notifications

    def _handle_callback_query(self, callback_query: dict) -> None:
        callback_id = callback_query["id"]
        data = callback_query.get("data", "")
        message = callback_query.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        from_user = callback_query.get("from", {})

        if data.startswith("resort:") and chat_id is not None:
            slug = data.split(":", 1)[1]
            self._answer_callback_query(callback_id)
            self._send_forecast(chat_id, slug, force=False, from_user=from_user, source="button")
            return

        if data.startswith("favorite:") and chat_id is not None and message_id is not None:
            slug = data.split(":", 1)[1]
            added, favorites = self._toggle_favorite_resort(from_user=from_user, chat_id=chat_id, slug=slug)
            self._answer_callback_query(
                callback_id,
                text="Курорт добавлен в избранное" if added else "Курорт убран из избранного",
            )
            self._edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self._favorites_picker_text(favorites),
                parse_mode="HTML",
                reply_markup=self._favorites_picker_markup(favorites),
            )
            return

        if data == "favorites:done" and chat_id is not None:
            self._answer_callback_query(callback_id)
            self._send_trip_settings(chat_id, from_user=from_user)
            return

        if data == "trip:toggle_notifications" and chat_id is not None and message_id is not None:
            enabled = self._toggle_notifications(from_user=from_user, chat_id=chat_id)
            user_context = self._get_user_context(from_user)
            self._answer_callback_query(
                callback_id,
                text="Уведомления включены" if enabled else "Уведомления выключены",
            )
            self._edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self._trip_settings_text(user_context["favorites"], user_context["trip_preferences"]),
                parse_mode="HTML",
                reply_markup=self._trip_settings_markup(user_context["trip_preferences"]),
            )
            return

        if data == "trip:set_dates" and chat_id is not None:
            self._answer_callback_query(callback_id)
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="awaiting_trip_dates",
                state_payload={},
                action_type="open_trip_dates_input",
                action_value=None,
            )
            self.send_message(
                chat_id,
                (
                    "Отправь диапазон дат в формате <code>28.03-30.03</code> или "
                    "<code>28.03.2026-30.03.2026</code>.\n"
                    "Если прогноз на эти даты пока не появился, я все равно сохраню диапазон."
                ),
                parse_mode="HTML",
                reply_markup=self._main_menu_markup(),
            )
            return

        if data == "trip:clear_dates" and chat_id is not None and message_id is not None:
            self._clear_trip_dates(from_user=from_user, chat_id=chat_id)
            user_context = self._get_user_context(from_user)
            self._answer_callback_query(callback_id, text="Даты поездки очищены")
            self._edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self._trip_settings_text(user_context["favorites"], user_context["trip_preferences"]),
                parse_mode="HTML",
                reply_markup=self._trip_settings_markup(user_context["trip_preferences"]),
            )
            return

        self._answer_callback_query(callback_id, text="Пока это действие не поддерживается.")

    def _answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        params = {"callback_query_id": callback_query_id}
        if text:
            params["text"] = text
        self._request("answerCallbackQuery", params)

    def _edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        params = {
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "text": text,
        }
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_markup is not None:
            params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        self._request("editMessageText", params)

    def _main_menu_markup(self) -> dict:
        return {
            "keyboard": [
                [{"text": SHOW_RESORTS_TEXT}, {"text": BEST_RESORT_TEXT}],
                [{"text": FAVORITES_TEXT}, {"text": TRIP_PLAN_TEXT}],
            ],
            "resize_keyboard": True,
        }

    def _send_favorites_picker(
        self,
        chat_id: int,
        *,
        from_user: dict | None = None,
        user_context: dict | None = None,
    ) -> None:
        if user_context is None:
            user_context = self._get_user_context(from_user)
        self.send_message(
            chat_id,
            self._favorites_picker_text(user_context["favorites"]),
            parse_mode="HTML",
            reply_markup=self._favorites_picker_markup(user_context["favorites"]),
        )

    def _favorites_picker_text(self, favorites: list[str]) -> str:
        favorites_text = ", ".join(self._resort_name(slug) for slug in favorites) if favorites else "пока нет"
        return (
            "<b>Избранные курорты</b>\n"
            "Отметь места, которые тебе реально интересны.\n\n"
            f"<i>Сейчас в избранном: {favorites_text}</i>"
        )

    def _favorites_picker_markup(self, favorites: list[str]) -> dict:
        favorite_set = set(favorites)
        keyboard = []
        for resort in self.resorts:
            prefix = "✅" if resort["slug"] in favorite_set else "◻️"
            keyboard.append(
                [
                    {
                        "text": f"{prefix} {resort['name']}",
                        "callback_data": f"favorite:{resort['slug']}",
                    }
                ]
            )
        keyboard.append([{"text": "Готово", "callback_data": "favorites:done"}])
        return {"inline_keyboard": keyboard}

    def _send_trip_settings(
        self,
        chat_id: int,
        *,
        from_user: dict | None = None,
        user_context: dict | None = None,
    ) -> None:
        if user_context is None:
            user_context = self._get_user_context(from_user)
        favorites = user_context["favorites"]
        if not favorites:
            self.send_message(
                chat_id,
                "Сначала добавь хотя бы один курорт в избранное, а потом уже можно включать уведомления и задавать даты поездки.",
                reply_markup=self._main_menu_markup(),
            )
            return
        self._track_user_state(
            from_user=from_user or {},
            chat_id=chat_id,
            current_state="trip_settings",
            state_payload={"favorites_count": len(favorites)},
            action_type="open_trip_plan",
            action_value="favorites_only",
        )
        self.send_message(
            chat_id,
            self._trip_settings_text(favorites, user_context["trip_preferences"]),
            parse_mode="HTML",
            reply_markup=self._trip_settings_markup(user_context["trip_preferences"]),
        )

    def _trip_settings_text(self, favorites: list[str], preferences: dict) -> str:
        favorite_names = ", ".join(self._resort_name(slug) for slug in favorites) or "пока нет"
        date_range = self._format_trip_date_range(
            preferences.get("start_date"),
            preferences.get("end_date"),
        )
        notifications_text = "включены" if preferences.get("notifications_enabled") else "выключены"
        return (
            "<b>План поездки</b>\n"
            f"<b>Избранные:</b> {favorite_names}\n"
            f"<b>Даты:</b> {date_range}\n"
            f"<b>Уведомления:</b> {notifications_text}\n\n"
            "Сохрани даты поездки, и я буду подбирать лучший курорт уже в этом окне."
        )

    def _trip_settings_markup(self, preferences: dict) -> dict:
        notifications_label = "Уведомления: вкл" if preferences.get("notifications_enabled") else "Уведомления: выкл"
        return {
            "inline_keyboard": [
                [{"text": "Задать даты поездки", "callback_data": "trip:set_dates"}],
                [{"text": notifications_label, "callback_data": "trip:toggle_notifications"}],
                [{"text": "Очистить даты", "callback_data": "trip:clear_dates"}],
            ]
        }

    def _handle_trip_dates_input(self, chat_id: int, text: str, *, from_user: dict | None) -> bool:
        normalized = text.strip().lower()
        if normalized in {"сброс", "очистить"}:
            self._clear_trip_dates(from_user=from_user, chat_id=chat_id)
            self.send_message(
                chat_id,
                "Даты поездки очищены.",
                reply_markup=self._main_menu_markup(),
            )
            return True

        parsed = self._parse_trip_date_range(text)
        if parsed is None:
            self.send_message(
                chat_id,
                "Не смог распознать даты. Попробуй формат <code>28.03-30.03</code> или <code>28.03.2026-30.03.2026</code>.",
                parse_mode="HTML",
                reply_markup=self._main_menu_markup(),
            )
            return True

        start_date, end_date = parsed
        preferences = self._get_trip_preferences(from_user)
        self.database.save_user_trip_preferences(
            telegram_user_id=self._telegram_user_id(from_user),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            notifications_enabled=preferences.get("notifications_enabled", False),
            updated_at=self._now_iso(),
        )
        self._track_user_state(
            from_user=from_user or {},
            chat_id=chat_id,
            current_state="trip_settings",
            state_payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            action_type="set_trip_dates",
            action_value=f"{start_date.isoformat()}:{end_date.isoformat()}",
        )
        self.send_message(
            chat_id,
            self._trip_settings_text(
                self._get_favorite_resorts(from_user),
                self._get_trip_preferences(from_user),
            ),
            parse_mode="HTML",
            reply_markup=self._trip_settings_markup(self._get_trip_preferences(from_user)),
        )
        return True

    def _toggle_favorite_resort(self, *, from_user: dict, chat_id: int, slug: str) -> tuple[bool, list[str]]:
        telegram_user_id = self._telegram_user_id(from_user)
        added, favorites = self.database.toggle_user_favorite_resort(
            telegram_user_id=telegram_user_id,
            resort_slug=slug,
            created_at=self._now_iso(),
        )
        self._track_user_state(
            from_user=from_user,
            chat_id=chat_id,
            current_state="managing_favorites",
            state_payload={"resort_slug": slug, "is_favorite": added},
            action_type="toggle_favorite_resort",
            action_value=slug,
        )
        return added, favorites

    def _toggle_notifications(self, *, from_user: dict, chat_id: int) -> bool:
        telegram_user_id = self._telegram_user_id(from_user)
        current = self.database.get_user_trip_preferences(telegram_user_id)
        enabled = not current["notifications_enabled"]
        self.database.set_user_notifications_enabled(
            telegram_user_id=telegram_user_id,
            notifications_enabled=enabled,
            updated_at=self._now_iso(),
        )
        self._track_user_state(
            from_user=from_user,
            chat_id=chat_id,
            current_state="trip_settings",
            state_payload={"notifications_enabled": enabled},
            action_type="toggle_notifications",
            action_value="on" if enabled else "off",
        )
        return enabled

    def _clear_trip_dates(self, *, from_user: dict | None, chat_id: int) -> None:
        if not from_user or "id" not in from_user:
            return
        self.database.clear_user_trip_dates(
            telegram_user_id=self._telegram_user_id(from_user),
            updated_at=self._now_iso(),
        )
        self._track_user_state(
            from_user=from_user,
            chat_id=chat_id,
            current_state="trip_settings",
            state_payload={"dates": None},
            action_type="clear_trip_dates",
            action_value=None,
        )

    def _get_favorite_resorts(self, from_user: dict | None) -> list[str]:
        if not from_user or "id" not in from_user:
            return []
        return self.database.list_user_favorite_resorts(str(from_user["id"]))

    def _get_trip_preferences(self, from_user: dict | None) -> dict:
        if not from_user or "id" not in from_user:
            return {
                "start_date": None,
                "end_date": None,
                "notifications_enabled": False,
            }
        return self.database.get_user_trip_preferences(str(from_user["id"]))

    def _get_current_user(self, from_user: dict | None) -> dict | None:
        return self._get_user_context(from_user)["user"]

    def _get_user_context(self, from_user: dict | None) -> dict:
        if not from_user or "id" not in from_user:
            return {
                "user": None,
                "favorites": [],
                "trip_preferences": {
                    "start_date": None,
                    "end_date": None,
                    "notifications_enabled": False,
                },
            }
        return self.database.get_user_context(str(from_user["id"]))

    def _telegram_user_id(self, from_user: dict | None) -> str:
        return str((from_user or {}).get("id", "unknown"))

    def _best_resort_scope_text(
        self,
        favorite_slugs: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> str:
        parts = []
        if favorite_slugs:
            parts.append(f"среди избранных: {', '.join(self._resort_name(slug) for slug in favorite_slugs)}")
        if start_date and end_date:
            parts.append(f"на даты {start_date.strftime('%d.%m')}–{end_date.strftime('%d.%m')}")
        return f"<i>{'; '.join(parts)}</i>" if parts else ""

    def _build_best_resort_message(
        self,
        result: dict,
        *,
        favorite_slugs: list[str],
        start_date: date | None,
        end_date: date | None,
        title: str,
    ) -> str:
        payload = result["payload"]
        reason = result["reasons"][0] if result["reasons"] else "лучшие условия по снегу и температуре"
        scope = self._best_resort_scope_text(favorite_slugs, start_date, end_date)
        parts = [f"<b>{title}</b>"]
        if scope:
            parts.append(scope)
        parts.append(f"<i>{reason}</i>")
        parts.append("")
        parts.append(format_telegram_resort_forecast(payload))
        return "\n".join(parts).strip()

    def _format_trip_date_range(self, start_date: str | None, end_date: str | None) -> str:
        if not start_date or not end_date:
            return "не заданы"
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        return f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}"

    def _parse_iso_date(self, value: str | None) -> date | None:
        if not value:
            return None
        return date.fromisoformat(value)

    def _parse_trip_date_range(self, raw: str) -> tuple[date, date] | None:
        normalized = raw.replace(" ", "")
        if "-" not in normalized:
            return None
        start_raw, end_raw = normalized.split("-", 1)
        start_date = self._parse_trip_date_part(start_raw)
        end_date = self._parse_trip_date_part(end_raw, default_year=start_date.year if start_date else None)
        if start_date is None or end_date is None or end_date < start_date:
            return None
        return start_date, end_date

    def _parse_trip_date_part(self, raw: str, default_year: int | None = None) -> date | None:
        parts = raw.split(".")
        try:
            if len(parts) == 2:
                return date(default_year or datetime.now(UTC).year, int(parts[1]), int(parts[0]))
            if len(parts) == 3:
                return date(int(parts[2]), int(parts[1]), int(parts[0]))
        except ValueError:
            return None
        return None

    def _resort_name(self, slug: str) -> str:
        return self.resort_names.get(slug, slug)

    def _request(self, method: str, params: dict[str, str]) -> dict:
        request = Request(
            f"{self.base_url}/{method}?{urlencode(params)}",
            headers={"Accept": "application/json"},
        )
        with urlopen(request, timeout=60, context=build_ssl_context()) as response:
            payload = json.load(response)
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        return payload

    def _track_user_state(
        self,
        *,
        from_user: dict,
        chat_id: int,
        current_state: str,
        state_payload: dict,
        action_type: str,
        action_value: str | None,
    ) -> None:
        if not from_user or "id" not in from_user:
            return

        timestamp = self._now_iso()
        telegram_user_id = str(from_user["id"])
        self.database.record_user_state(
            telegram_user_id=telegram_user_id,
            chat_id=str(chat_id),
            username=from_user.get("username"),
            first_name=from_user.get("first_name"),
            last_name=from_user.get("last_name"),
            current_state=current_state,
            state_payload=state_payload,
            action_type=action_type,
            action_value=action_value,
            created_at=timestamp,
        )

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat()
