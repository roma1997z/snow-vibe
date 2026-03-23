from __future__ import annotations

from datetime import date, datetime
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

    def get_best_resort(
        self,
        *,
        force: bool = False,
        resort_slugs: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict | None:
        scored = []
        candidate_slugs = resort_slugs or sorted(RESORTS)
        for slug in sorted(candidate_slugs):
            payload = self.get_forecast(slug, force=force)
            score, reasons = self._score_resort(
                payload,
                start_date=start_date,
                end_date=end_date,
            )
            if score is None:
                continue
            scored.append(
                {
                    "slug": slug,
                    "payload": payload,
                    "score": score,
                    "reasons": reasons,
                }
            )

        if not scored:
            return None
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[0]

    def _fetch_spot_forecast(self, provider: str, resort, spot):
        if provider == "met.no":
            return self.metno.fetch_spot_forecast(resort, spot)
        raise ValueError(f"Unsupported provider: {provider}")

    def _score_resort(
        self,
        payload: dict,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[float | None, list[str]]:
        score = 0.0
        reasons: list[str] = []
        best_snow_day = None
        worst_rain_day = None
        scored_days = 0

        for spot_index, spot in enumerate(payload["spots"]):
            spot_name = spot["spot"]["name"]
            spot_weight = 1.15 if spot_index > 0 else 1.0
            daily_days = self._select_daily_days(
                spot["daily"],
                start_date=start_date,
                end_date=end_date,
            )
            for day_index, day in enumerate(daily_days):
                precip = day["total_precip_mm"] or 0.0
                max_temp = day["max_temp_c"]
                min_temp = day["min_temp_c"]
                proximity_weight = 1.4 if day_index == 0 else 1.2 if day_index == 1 else 1.0
                day_score = 0.0

                if max_temp is not None:
                    if max_temp <= -4:
                        day_score += 2.5 * proximity_weight
                    elif max_temp <= -1:
                        day_score += 1.8 * proximity_weight
                    elif max_temp <= 0:
                        day_score += 1.0 * proximity_weight
                    elif max_temp > 2:
                        day_score -= 2.4 * proximity_weight
                    else:
                        day_score -= 1.0 * proximity_weight

                if min_temp is not None and min_temp <= -7:
                    day_score += 0.8 * proximity_weight

                if precip >= 1 and max_temp is not None and max_temp <= 0:
                    snowfall_bonus = (2.2 + precip * 1.3) * proximity_weight * spot_weight
                    day_score += snowfall_bonus
                    candidate = (
                        snowfall_bonus,
                        f'{day["day"]} {spot_name}: снег {_format_number(precip)} мм, '
                        f'{_format_temperature(min_temp)}…{_format_temperature(max_temp)}',
                    )
                    if best_snow_day is None or candidate[0] > best_snow_day[0]:
                        best_snow_day = candidate
                elif precip >= 1 and max_temp is not None and min_temp is not None and min_temp <= 0 < max_temp:
                    rain_penalty = (1.5 + precip * 1.2) * proximity_weight
                    day_score -= rain_penalty
                    candidate = (
                        rain_penalty,
                        f'{day["day"]} {spot_name}: риск дождя, {_format_temperature(min_temp)}…{_format_temperature(max_temp)}',
                    )
                    if worst_rain_day is None or candidate[0] > worst_rain_day[0]:
                        worst_rain_day = candidate
                elif precip >= 1 and max_temp is not None and max_temp > 0:
                    rain_penalty = (2.0 + precip * 1.5) * proximity_weight
                    day_score -= rain_penalty
                    candidate = (
                        rain_penalty,
                        f'{day["day"]} {spot_name}: дождь при {_format_temperature(max_temp)}',
                    )
                    if worst_rain_day is None or candidate[0] > worst_rain_day[0]:
                        worst_rain_day = candidate

                score += day_score * spot_weight
                scored_days += 1

        if scored_days == 0:
            return None, ["На выбранные даты пока нет прогноза."]
        if best_snow_day is not None:
            reasons.insert(0, best_snow_day[1])
        elif worst_rain_day is not None:
            reasons.append(worst_rain_day[1])
        if score <= 0 and not reasons:
            reasons.append("В ближайшие дни нет явного снегопада при минусовой температуре.")
        return score, reasons

    def _select_daily_days(
        self,
        daily: list[dict],
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> list[dict]:
        if start_date is None and end_date is None:
            return daily[:3]

        selected = []
        for day in daily:
            day_date = date.fromisoformat(day["day"])
            if start_date is not None and day_date < start_date:
                continue
            if end_date is not None and day_date > end_date:
                continue
            selected.append(day)
        return selected


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
