from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from snow_vibe.models import SpotForecast


def serialize_spot_forecast(forecast: SpotForecast) -> dict:
    payload = asdict(forecast)
    payload["updated_at"] = forecast.updated_at.isoformat()
    payload["local_timezone"] = forecast.resort.timezone

    for hourly in payload["hourly"]:
        hourly["time"] = hourly["time"].isoformat()

    for daily in payload["daily"]:
        daily["day"] = daily["day"].isoformat()

    return payload


def build_resort_payload(*, resort_slug: str, provider: str, forecasts: list[SpotForecast]) -> dict:
    timezone = forecasts[0].resort.timezone if forecasts else "UTC"
    return {
        "resort_slug": resort_slug,
        "provider": provider,
        "local_timezone": timezone,
        "spots": [serialize_spot_forecast(item) for item in forecasts],
    }


def summarize_resort_payload(payload: dict) -> str:
    lines = []
    for spot in payload["spots"]:
        now = spot["hourly"][0] if spot["hourly"] else None
        lines.append(f'{spot["resort"]["name"]} / {spot["spot"]["name"]}')
        lines.append(f'  updated_at: {spot["updated_at"]}')
        lines.append(f'  elevation_m: {spot["elevation_m"]}')
        if now:
            lines.append(
                "  now: "
                f'{now["temperature_c"]}C, '
                f'wind {now["wind_speed_mps"]} m/s, '
                f'precip {now["precipitation_mm"]} mm, '
                f'symbol {now["symbol_code"]}'
            )
        for day in spot["daily"][:3]:
            lines.append(
                "  day: "
                f'{day["day"]} '
                f'min={day["min_temp_c"]}C '
                f'max={day["max_temp_c"]}C '
                f'precip={day["total_precip_mm"]}mm '
                f'freeze_hours={day["freeze_hours"]}'
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def resort_local_date(payload: dict) -> str:
    timezone = ZoneInfo(payload.get("local_timezone", "UTC"))
    first_spot = payload["spots"][0]
    updated_at = first_spot["updated_at"]

    return datetime.fromisoformat(updated_at).astimezone(timezone).date().isoformat()


def format_telegram_resort_forecast(payload: dict) -> str:
    if not payload["spots"]:
        return "Нет данных по курорту."

    timezone = ZoneInfo(payload.get("local_timezone", "UTC"))
    first_spot = payload["spots"][0]
    resort_name = escape(first_spot["resort"]["name"])
    updated_at = datetime.fromisoformat(first_spot["updated_at"]).astimezone(timezone)

    lines = [
        f"<b>{resort_name}</b>",
        f"<i>Обновлено: {updated_at.strftime('%d.%m %H:%M')}</i>",
        "",
    ]

    for spot in payload["spots"]:
        spot_name = escape(spot["spot"]["name"])
        elevation = spot["elevation_m"]
        lines.append(f"<b>{spot_name}</b> • {elevation} м")
        lines.append("<code>Дата    Температура      Осадки</code>")

        for day in spot["daily"][:3]:
            label = _format_short_date(day["day"])
            temp_range = _format_temperature_range(day["min_temp_c"], day["max_temp_c"])
            precip = _format_precipitation(day["min_temp_c"], day["max_temp_c"], day["total_precip_mm"])
            lines.append(
                f"<code>{label}  {temp_range:<15} {precip:>7}</code>"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_temperature(value: float | None) -> str:
    if value is None:
        return "n/a"
    rounded = round(value, 1)
    return f"{rounded:+g}°C"


def _format_temperature_range(min_temp: float | None, max_temp: float | None) -> str:
    return f"{_format_temperature(min_temp)}…{_format_temperature(max_temp)}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    rounded = round(value, 1)
    if rounded.is_integer():
        return str(int(rounded))
    return str(rounded)


def _format_short_date(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%d.%m")


def _format_precipitation(
    min_temp: float | None,
    max_temp: float | None,
    precip_mm: float | None,
) -> str:
    amount = precip_mm or 0.0
    if amount < 1:
        return "-"
    if max_temp is not None and max_temp > 0:
        return "дождь"
    return f"{_format_number(amount)} мм"
