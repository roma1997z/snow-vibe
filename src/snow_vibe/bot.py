from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from snow_vibe.config import get_telegram_bot_token, get_telegram_webhook_secret
from snow_vibe.http import build_ssl_context
from snow_vibe.serialization import format_telegram_resort_forecast
from snow_vibe.services import ForecastService
from snow_vibe.storage import Database


SHOW_RESORTS_TEXT = "Показать курорты"
BEST_RESORT_TEXT = "Выбрать лучший курорт"

WELCOME_TEXT = (
    "<b>snow vibe</b>\n"
    "Выбери действие в меню ниже.\n\n"
    "Сейчас можно посмотреть доступные курорты и получить прогноз на сегодня, завтра и послезавтра."
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
        resorts = self.service.list_resorts()
        keyboard = [
            [{"text": resort["name"], "callback_data": f'resort:{resort["slug"]}'}]
            for resort in resorts
        ]
        self.send_message(
            chat_id,
            "Выбери курорт:",
            reply_markup={"inline_keyboard": keyboard},
        )

    def _send_best_resort(self, chat_id: int, *, from_user: dict | None = None) -> None:
        result = self.service.get_best_resort(force=False)
        payload = result["payload"]
        reason = result["reasons"][0] if result["reasons"] else "лучшие условия по снегу и температуре"
        best_slug = result["slug"]
        if from_user is not None:
            self._track_user_state(
                from_user=from_user,
                chat_id=chat_id,
                current_state="viewing_best_resort",
                state_payload={"resort_slug": best_slug, "reason": reason},
                action_type="choose_best_resort",
                action_value=best_slug,
            )
        text = (
            f"<b>Лучший курорт сейчас</b>\n"
            f"<i>{reason}</i>\n\n"
            f"{format_telegram_resort_forecast(payload)}"
        )
        self.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
        )

    def _handle_callback_query(self, callback_query: dict) -> None:
        callback_id = callback_query["id"]
        data = callback_query.get("data", "")
        message = callback_query.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        from_user = callback_query.get("from", {})

        if data.startswith("resort:") and chat_id is not None:
            slug = data.split(":", 1)[1]
            self._answer_callback_query(callback_id)
            self._send_forecast(chat_id, slug, force=False, from_user=from_user, source="button")
            return

        self._answer_callback_query(callback_id, text="Пока это действие не поддерживается.")

    def _answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        params = {"callback_query_id": callback_query_id}
        if text:
            params["text"] = text
        self._request("answerCallbackQuery", params)

    def _main_menu_markup(self) -> dict:
        return {
            "keyboard": [
                [{"text": SHOW_RESORTS_TEXT}],
                [{"text": BEST_RESORT_TEXT}],
            ],
            "resize_keyboard": True,
        }

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

        timestamp = datetime.now(UTC).isoformat()
        telegram_user_id = str(from_user["id"])
        self.database.upsert_telegram_user(
            telegram_user_id=telegram_user_id,
            chat_id=str(chat_id),
            username=from_user.get("username"),
            first_name=from_user.get("first_name"),
            last_name=from_user.get("last_name"),
            current_state=current_state,
            state_payload=state_payload,
            last_action=action_type,
            last_seen_at=timestamp,
        )
        self.database.log_user_action(
            telegram_user_id=telegram_user_id,
            chat_id=str(chat_id),
            action_type=action_type,
            action_value=action_value,
            created_at=timestamp,
        )
