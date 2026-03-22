from __future__ import annotations

from datetime import datetime
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

    def _fetch_spot_forecast(self, provider: str, resort, spot):
        if provider == "met.no":
            return self.metno.fetch_spot_forecast(resort, spot)
        raise ValueError(f"Unsupported provider: {provider}")
