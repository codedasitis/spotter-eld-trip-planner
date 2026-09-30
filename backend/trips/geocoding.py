"""
trips/geocoding.py

Nominatim (OpenStreetMap) geocoding client. Zero-cost, no API key -- and
therefore rate-limited and usage-policy-gated, which is why every request
carries the required User-Agent header and every input is bounded before
it leaves this process.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_TIMEOUT_SECONDS = 8
MAX_QUERY_LENGTH = 200

# Nominatim's usage policy requires a real, identifying User-Agent -- omit
# it and requests get silently rate-limited (HTTP 200 with zero results),
# which looks exactly like "location not found" and is miserable to debug
# under demo conditions.
USER_AGENT = "SpotterAI-Assessment/1.0"


class GeocodingError(Exception):
    """Raised when a location string cannot be resolved to coordinates."""


@dataclass
class GeocodedLocation:
    display_name: str
    latitude: float
    longitude: float


def geocode(location_text: str) -> GeocodedLocation:
    if not location_text or not location_text.strip():
        raise GeocodingError("Location not found. Please enter a city and state.")

    # Bound the input before it ever reaches an external HTTP call -- this
    # is a defensive cap, not a UX validation message (the serializer
    # already enforces a sane max_length on the field).
    safe_query = location_text.strip()[:MAX_QUERY_LENGTH]

    params = {"q": safe_query, "format": "json", "limit": 1, "countrycodes": "us"}
    headers = {"User-Agent": USER_AGENT}

    try:
        # `requests` handles URL-encoding of `params` itself -- encoding
        # `safe_query` again here would double-escape it and break lookups
        # for any location containing a space or comma (i.e. almost all of
        # them).
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=NOMINATIM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.Timeout, requests.RequestException, ValueError) as exc:
        raise GeocodingError("Location not found. Please enter a city and state.") from exc

    if not results:
        raise GeocodingError("Location not found. Please enter a city and state.")

    top = results[0]
    return GeocodedLocation(
        display_name=top.get("display_name", safe_query),
        latitude=float(top["lat"]),
        longitude=float(top["lon"]),
    )
