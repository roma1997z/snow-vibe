from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from snow_vibe.config import get_user_agent
from snow_vibe.http import build_ssl_context
from snow_vibe.models import DailyForecast, HourlyForecast, Resort, ResortSpot, SpotForecast


class MetNoClient:
    base_url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"

    def fetch_spot_forecast(self, resort: Resort, spot: ResortSpot) -> SpotForecast:
        query = urlencode({"lat": spot.coordinates.lat, "lon": spot.coordinates.lon})
        request = Request(
            f"{self.base_url}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": get_user_agent(),
            },
        )
        with urlopen(request, timeout=20, context=build_ssl_context()) as response:
            payload = json.load(response)
        return self._parse_forecast(resort=resort, spot=spot, payload=payload)

    def _parse_forecast(
        self,
        *,
        resort: Resort,
        spot: ResortSpot,
        payload: dict[str, Any],
    ) -> SpotForecast:
        properties = payload["properties"]
        updated_at = _parse_datetime(properties["meta"]["updated_at"])
        elevation = payload.get("geometry", {}).get("coordinates", [None, None, None])[2]

        hourly: list[HourlyForecast] = []
        for item in properties["timeseries"]:
            details = item["data"]["instant"]["details"]
            next_hour = item["data"].get("next_1_hours", {})
            hourly.append(
                HourlyForecast(
                    time=_parse_datetime(item["time"]),
                    temperature_c=details.get("air_temperature"),
                    precipitation_mm=next_hour.get("details", {}).get("precipitation_amount"),
                    wind_speed_mps=details.get("wind_speed"),
                    wind_direction_deg=details.get("wind_from_direction"),
                    cloud_area_fraction=details.get("cloud_area_fraction"),
                    relative_humidity=details.get("relative_humidity"),
                    symbol_code=next_hour.get("summary", {}).get("symbol_code"),
                )
            )

        return SpotForecast(
            resort=resort,
            spot=spot,
            updated_at=updated_at,
            elevation_m=elevation,
            hourly=tuple(hourly),
            daily=_build_daily_forecasts(hourly, timezone_name=resort.timezone),
        )


def _build_daily_forecasts(
    hourly: list[HourlyForecast],
    *,
    timezone_name: str = "UTC",
) -> tuple[DailyForecast, ...]:
    tz = ZoneInfo(timezone_name)
    grouped: dict[date, list[HourlyForecast]] = defaultdict(list)
    for item in hourly:
        grouped[item.time.astimezone(tz).date()].append(item)

    daily: list[DailyForecast] = []
    for day in sorted(grouped):
        entries = grouped[day]
        temps = [value.temperature_c for value in entries if value.temperature_c is not None]
        winds = [value.wind_speed_mps for value in entries if value.wind_speed_mps is not None]
        total_precip = sum(value.precipitation_mm or 0.0 for value in entries)
        freeze_hours = sum(
            1 for value in entries if value.temperature_c is not None and value.temperature_c <= 0
        )
        daily.append(
            DailyForecast(
                day=day,
                min_temp_c=min(temps) if temps else None,
                max_temp_c=max(temps) if temps else None,
                total_precip_mm=round(total_precip, 2),
                max_wind_mps=max(winds) if winds else None,
                freeze_hours=freeze_hours,
            )
        )
    return tuple(daily)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
