from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from snow_vibe.config import get_user_agent
from snow_vibe.http import build_ssl_context
from snow_vibe.models import GeocodeResult


class NominatimClient:
    base_url = "https://nominatim.openstreetmap.org/search"

    def search(self, query: str, *, limit: int = 5) -> list[GeocodeResult]:
        params = urlencode(
            {
                "q": query,
                "format": "jsonv2",
                "limit": str(limit),
            }
        )
        request = Request(
            f"{self.base_url}?{params}",
            headers={
                "Accept": "application/json",
                "User-Agent": get_user_agent(),
            },
        )
        with urlopen(request, timeout=20, context=build_ssl_context()) as response:
            payload = json.load(response)

        return [
            GeocodeResult(
                query=query,
                display_name=item["display_name"],
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                category=item.get("category"),
                result_type=item.get("type"),
            )
            for item in payload
        ]
