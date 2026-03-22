from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from snow_vibe.providers.metno import MetNoClient
from snow_vibe.resorts import RESORTS, get_resort
from snow_vibe.serialization import build_resort_payload
from snow_vibe.storage import Database


class ForecastService:
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()
        self.metno = MetNoClient()

    def list_resorts(self) -> list[dict]:
        return [
            {
                "slug": resort.slug,
                "name": resort.name,
                "provider": resort.provider,
                "timezone": resort.timezone,
                "spots": [
                    {
                        "slug": spot.slug,
                        "name": spot.name,
                        "lat": spot.coordinates.lat,
                        "lon": spot.coordinates.lon,
                    }
                    for spot in resort.spots
                ],
            }
            for resort in RESORTS.values()
        ]

    def get_forecast(self, resort_slug: str, *, force: bool = False) -> dict:
        resort = get_resort(resort_slug)
        today = datetime.now(ZoneInfo(resort.timezone)).date()

        if not force:
            cached = self.database.get_cached_forecast(resort_slug, today)
            if cached is not None:
                return cached

        forecasts = [self._fetch_spot_forecast(resort.provider, resort, spot) for spot in resort.spots]
        payload = build_resort_payload(
            resort_slug=resort.slug,
            provider=resort.provider,
            forecasts=forecasts,
        )
        self.database.save_forecast(
            resort_slug=resort.slug,
            cache_date=today,
            provider=resort.provider,
            payload=payload,
            fetched_at=datetime.now(tz=ZoneInfo("UTC")),
        )
        return payload

    def refresh_all(self) -> list[dict]:
        return [self.get_forecast(slug, force=True) for slug in sorted(RESORTS)]

    def get_best_resort(self, *, force: bool = False) -> dict:
        scored = []
        for slug in sorted(RESORTS):
            payload = self.get_forecast(slug, force=force)
            score, reasons = self._score_resort(payload)
            scored.append(
                {
                    "slug": slug,
                    "payload": payload,
                    "score": score,
                    "reasons": reasons,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return {
            "best": scored[0],
            "ranking": scored,
        }

    def _fetch_spot_forecast(self, provider: str, resort, spot):
        if provider == "met.no":
            return self.metno.fetch_spot_forecast(resort, spot)
        raise ValueError(f"Unsupported provider: {provider}")

    def _score_resort(self, payload: dict) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        best_snow_day = None

        for spot in payload["spots"]:
            spot_name = spot["spot"]["name"]
            for day in spot["daily"][:3]:
                precip = day["total_precip_mm"] or 0.0
                max_temp = day["max_temp_c"]
                min_temp = day["min_temp_c"]

                if precip >= 1 and max_temp is not None and max_temp <= 0:
                    day_score = precip + 2.0
                    score += day_score
                    candidate = (
                        day_score,
                        f'{day["day"]} {spot_name}: снег {_format_number(precip)} мм, '
                        f'{_format_temperature(min_temp)}…{_format_temperature(max_temp)}',
                    )
                    if best_snow_day is None or candidate[0] > best_snow_day[0]:
                        best_snow_day = candidate
                elif precip >= 1 and max_temp is not None and max_temp > 0:
                    score -= precip
                    reasons.append(
                        f'{day["day"]} {spot_name}: дождь при {_format_temperature(max_temp)}'
                    )

        if best_snow_day is not None:
            reasons.insert(0, best_snow_day[1])
        if score <= 0 and not reasons:
            reasons.append("В ближайшие дни нет явного снегопада при минусовой температуре.")
        return score, reasons


def format_best_resort_message(result: dict) -> str:
    best = result["best"]
    payload = best["payload"]
    resort_name = escape(payload["spots"][0]["resort"]["name"])

    lines = [
        f"<b>Лучший курорт сейчас: {resort_name}</b>",
        f"<i>Score: {_format_number(best['score'])}</i>",
        "",
    ]
    for reason in best["reasons"][:3]:
        lines.append(f"• {escape(reason)}")

    lines.append("")
    lines.append("<b>Топ курортов</b>")
    for item in result["ranking"]:
        name = escape(item["payload"]["spots"][0]["resort"]["name"])
        lines.append(f"• {name}: {_format_number(item['score'])}")

    return "\n".join(lines)


def _format_temperature(value: float | None) -> str:
    if value is None:
        return "n/a"
    rounded = round(value, 1)
    return f"{rounded:+g}°C"


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    rounded = round(value, 1)
    if rounded.is_integer():
        return str(int(rounded))
    return str(rounded)
