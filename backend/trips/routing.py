"""
trips/routing.py

Thin routing client: OSRM public demo server, with an explicit, clearly
labeled haversine straight-line fallback when OSRM is slow, down, or
returns something unusable. This module never silently substitutes one
for the other -- callers always get told which source was actually used
(`RouteResult.source`), and that flag rides all the way to the frontend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import requests

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
OSRM_TIMEOUT_SECONDS = 8

HAVERSINE_ASSUMED_SPEED_MPH = 55.0
EARTH_RADIUS_MILES = 3958.8

# Real-road distance is essentially never a straight line. When we fall
# back to haversine (which *is* a straight line), we inflate the raw
# great-circle distance by this factor to approximate real routing
# distance. This is a rough, named heuristic, not a substitute for real
# routing data -- which is exactly why the fallback is always surfaced to
# the user instead of hidden.
HAVERSINE_ROAD_FACTOR = 1.25


class RoutingSource:
    OSRM = "osrm"
    HAVERSINE_FALLBACK = "haversine_fallback"


@dataclass
class RouteLegResult:
    distance_miles: float
    duration_hours: float


@dataclass
class RouteResult:
    source: str
    total_distance_miles: float
    total_duration_hours: float
    legs: list  # list[RouteLegResult], one per consecutive waypoint pair
    geometry: list | None  # list[[lat, lon], ...] polyline, or None for fallback


def haversine_distance_miles(coord_a: tuple, coord_b: tuple) -> float:
    """Great-circle distance between two (lat, lon) pairs, in miles."""
    lat1, lon1 = coord_a
    lat2, lon2 = coord_b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def _haversine_route(waypoints: list) -> RouteResult:
    legs = []
    total_miles = 0.0
    for a, b in zip(waypoints, waypoints[1:]):
        straight_line = haversine_distance_miles(a, b)
        road_estimate = straight_line * HAVERSINE_ROAD_FACTOR
        duration = road_estimate / HAVERSINE_ASSUMED_SPEED_MPH
        legs.append(RouteLegResult(distance_miles=road_estimate, duration_hours=duration))
        total_miles += road_estimate

    return RouteResult(
        source=RoutingSource.HAVERSINE_FALLBACK,
        total_distance_miles=total_miles,
        total_duration_hours=sum(l.duration_hours for l in legs),
        legs=legs,
        geometry=None,  # frontend draws a straight line between waypoints instead
    )


def get_route(waypoints: list) -> RouteResult:
    """
    waypoints: list of (lat, lon) tuples, in visit order (>= 2 points).
    Returns a RouteResult. Never raises for routing failures -- OSRM
    timeouts, 5xx responses, and empty/malformed routes all fall back to
    the haversine estimate rather than bubbling an exception up to the API
    layer, because a demo with no live network access to OSRM should still
    produce a usable trip plan.
    """
    if len(waypoints) < 2:
        raise ValueError("get_route requires at least two waypoints.")

    coords = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
    url = f"{OSRM_BASE_URL}/{coords}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    try:
        response = requests.get(url, params=params, timeout=OSRM_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except (requests.Timeout, requests.RequestException, ValueError):
        return _haversine_route(waypoints)

    routes = data.get("routes") or []
    if not routes:
        return _haversine_route(waypoints)

    route = routes[0]
    legs_data = route.get("legs") or []
    if not legs_data:
        return _haversine_route(waypoints)

    legs = [
        RouteLegResult(
            distance_miles=leg["distance"] / 1609.344,
            duration_hours=leg["duration"] / 3600.0,
        )
        for leg in legs_data
    ]

    geometry_coords = (route.get("geometry") or {}).get("coordinates") or []
    # GeoJSON is [lon, lat]; the frontend (Leaflet) wants [lat, lon].
    geometry = [[lat, lon] for lon, lat in geometry_coords] or None

    return RouteResult(
        source=RoutingSource.OSRM,
        total_distance_miles=route["distance"] / 1609.344,
        total_duration_hours=route["duration"] / 3600.0,
        legs=legs,
        geometry=geometry,
    )


def point_at_distance(polyline_points: list, target_miles: float) -> tuple:
    """
    Walk a polyline (list of (lat, lon)) and return the interpolated point
    at `target_miles` along it. Used to place REST/FUEL/BREAK markers on
    the map at roughly the right spot along the route, since those stops
    don't have their own geocoded address -- only "how far into the trip"
    they occur.
    """
    if not polyline_points:
        raise ValueError("point_at_distance requires at least one point.")
    if len(polyline_points) == 1 or target_miles <= 0:
        return polyline_points[0]

    covered = 0.0
    for a, b in zip(polyline_points, polyline_points[1:]):
        segment_miles = haversine_distance_miles(a, b)
        if covered + segment_miles >= target_miles or segment_miles <= 0:
            remaining = target_miles - covered
            fraction = 0.0 if segment_miles <= 0 else min(max(remaining / segment_miles, 0.0), 1.0)
            lat = a[0] + (b[0] - a[0]) * fraction
            lon = a[1] + (b[1] - a[1]) * fraction
            return (lat, lon)
        covered += segment_miles

    return polyline_points[-1]
