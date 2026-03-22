from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Coordinates:
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class ResortSpot:
    slug: str
    name: str
    coordinates: Coordinates
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Resort:
    slug: str
    name: str
    provider: str
    coordinates: Coordinates
    address: str
    timezone: str
    spots: tuple[ResortSpot, ...]


@dataclass(frozen=True, slots=True)
class HourlyForecast:
    time: datetime
    temperature_c: float | None
    precipitation_mm: float | None
    wind_speed_mps: float | None
    wind_direction_deg: float | None
    cloud_area_fraction: float | None
    relative_humidity: float | None
    symbol_code: str | None


@dataclass(frozen=True, slots=True)
class DailyForecast:
    day: date
    min_temp_c: float | None
    max_temp_c: float | None
    total_precip_mm: float
    max_wind_mps: float | None
    freeze_hours: int


@dataclass(frozen=True, slots=True)
class SpotForecast:
    resort: Resort
    spot: ResortSpot
    updated_at: datetime
    elevation_m: float | None
    hourly: tuple[HourlyForecast, ...]
    daily: tuple[DailyForecast, ...]


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    query: str
    display_name: str
    lat: float
    lon: float
    category: str | None
    result_type: str | None
