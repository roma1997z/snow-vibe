from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from snow_vibe.bot import TelegramBot
from snow_vibe.geocoding import NominatimClient
from snow_vibe.serialization import summarize_resort_payload
from snow_vibe.resorts import RESORTS, get_resort
from snow_vibe.services import ForecastService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snow-vibe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    forecast_parser = subparsers.add_parser("forecast", help="Fetch forecast for a resort")
    forecast_parser.add_argument("resort", choices=sorted(RESORTS))
    forecast_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print a short human-readable summary instead of JSON.",
    )
    forecast_parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore today's cache and refresh from the upstream provider.",
    )

    geocode_parser = subparsers.add_parser("geocode", help="Resolve coordinates by text query")
    geocode_parser.add_argument("query")

    subparsers.add_parser("refresh-all", help="Refresh all configured resorts")
    subparsers.add_parser("bot-poll", help="Run Telegram bot long polling")
    webhook_set_parser = subparsers.add_parser("set-webhook", help="Register Telegram webhook URL")
    webhook_set_parser.add_argument("url")
    webhook_set_parser.add_argument(
        "--keep-pending",
        action="store_true",
        help="Do not drop pending updates when setting the webhook.",
    )
    subparsers.add_parser("webhook-info", help="Show Telegram webhook status")
    webhook_delete_parser = subparsers.add_parser(
        "delete-webhook",
        help="Remove Telegram webhook and optionally drop pending updates",
    )
    webhook_delete_parser.add_argument(
        "--drop-pending",
        action="store_true",
        help="Drop pending updates while removing the webhook.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "forecast":
        _run_forecast(args.resort, pretty=args.pretty, force=args.force)
        return
    if args.command == "geocode":
        _run_geocode(args.query)
        return
    if args.command == "refresh-all":
        _run_refresh_all()
        return
    if args.command == "bot-poll":
        _run_bot_poll()
        return
    if args.command == "set-webhook":
        _run_set_webhook(args.url, keep_pending=args.keep_pending)
        return
    if args.command == "webhook-info":
        _run_webhook_info()
        return
    if args.command == "delete-webhook":
        _run_delete_webhook(drop_pending=args.drop_pending)
        return
    parser.error(f"Unsupported command: {args.command}")


def _run_forecast(resort_slug: str, *, pretty: bool, force: bool) -> None:
    get_resort(resort_slug)
    payload = ForecastService().get_forecast(resort_slug, force=force)
    if pretty:
        print(summarize_resort_payload(payload))
        return

    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_geocode(query: str) -> None:
    client = NominatimClient()
    results = [asdict(item) for item in client.search(query)]
    print(json.dumps(results, ensure_ascii=False, indent=2))


def _run_refresh_all() -> None:
    payload = ForecastService().refresh_all()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_bot_poll() -> None:
    TelegramBot().run_polling()


def _run_set_webhook(url: str, *, keep_pending: bool) -> None:
    payload = TelegramBot().set_webhook(url, drop_pending_updates=not keep_pending)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_webhook_info() -> None:
    payload = TelegramBot().get_webhook_info()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_delete_webhook(*, drop_pending: bool) -> None:
    payload = TelegramBot().delete_webhook(drop_pending_updates=drop_pending)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
