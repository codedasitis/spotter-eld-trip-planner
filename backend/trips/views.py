"""
trips/views.py

Wires the three pieces together for POST /api/v1/trip/plan/:
    1. geocoding.geocode()      -- location strings -> coordinates
    2. routing.get_route()      -- coordinates -> distances/durations/geometry
    3. hos_engine.TripPlanner   -- distances/durations -> a full HOS-compliant plan

This module owns zero HOS business logic itself. If you find yourself
writing an `if` statement here that mentions hours, miles, or duty
status, it belongs in hos_engine.py instead.
"""

import uuid

from rest_framework.response import Response
from rest_framework.views import APIView

from . import routing
from .geocoding import GeocodingError, geocode
from .hos_engine import HOSViolationError, TripLeg, TripPlanner
from .serializers import TripPlanRequestSerializer

APP_VERSION = "1.0.0"


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok", "version": APP_VERSION})


class TripPlanView(APIView):
    def post(self, request):
        request_serializer = TripPlanRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=400)

        data = request_serializer.validated_data

        try:
            TripPlanner.validate_cycle_hours(data["current_cycle_used"])
        except HOSViolationError as exc:
            # Fail fast: an exhausted cycle can never be planned, so don't
            # spend a geocoding or routing call finding that out.
            return Response({"current_cycle_used": [str(exc)]}, status=422)

        geocoded = {}
        field_errors = {}
        for field_name, location_key in (
            ("current_location", "current"),
            ("pickup_location", "pickup"),
            ("dropoff_location", "dropoff"),
        ):
            try:
                geocoded[location_key] = geocode(data[field_name])
            except GeocodingError as exc:
                field_errors[field_name] = [str(exc)]

        if field_errors:
            return Response(field_errors, status=422)

        waypoints = [
            (geocoded["current"].latitude, geocoded["current"].longitude),
            (geocoded["pickup"].latitude, geocoded["pickup"].longitude),
            (geocoded["dropoff"].latitude, geocoded["dropoff"].longitude),
        ]
        route = routing.get_route(waypoints)

        legs = [
            TripLeg(
                start_location=data["current_location"],
                end_location=data["pickup_location"],
                distance_miles=route.legs[0].distance_miles,
                duration_hours=route.legs[0].duration_hours,
            ),
            TripLeg(
                start_location=data["pickup_location"],
                end_location=data["dropoff_location"],
                distance_miles=route.legs[1].distance_miles,
                duration_hours=route.legs[1].duration_hours,
            ),
        ]

        try:
            planner = TripPlanner(
                current_location=data["current_location"],
                pickup_location=data["pickup_location"],
                dropoff_location=data["dropoff_location"],
                current_cycle_used=data["current_cycle_used"],
                legs=legs,
                start_datetime=_next_business_start(),
                home_terminal=data["current_location"],
            )
            result = planner.plan()
        except HOSViolationError as exc:
            return Response({"current_cycle_used": [str(exc)]}, status=422)

        combined_polyline = route.geometry or waypoints
        stops = _build_stop_markers(result.days, combined_polyline, route.total_distance_miles)

        payload = {
            "trip_id": str(uuid.uuid4()),
            "total_distance_miles": result.total_distance_miles,
            "total_driving_hours": result.total_driving_hours,
            "total_trip_hours": result.total_trip_hours,
            "routing_source": route.source,
            "route_geometry": route.geometry,
            "stops": stops,
            "days": result.days,
            "log_sheets": result.log_sheets,
        }
        return Response(payload, status=200)


def _next_business_start():
    """
    The assessment gives no explicit departure timestamp, only trip
    inputs. Rather than starting the plan at the literal current second
    (which could land at 3 a.m. and produce a confusing first log sheet),
    default to the next 08:00: today's if it hasn't passed yet, tomorrow's
    otherwise. This is a product default, not an HOS rule.
    """
    from datetime import datetime, timedelta

    now = datetime.now()
    candidate = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _build_stop_markers(days: list, polyline: list, total_distance_miles: float) -> list:
    """
    Every non-drive, non-padding segment becomes a map marker. Since only
    PICKUP/DROPOFF are geocoded to a real address, REST/FUEL/BREAK/RESTART
    stops are placed by interpolating along the route polyline at however
    many cumulative miles into the trip they occur.
    """
    stops = []
    cumulative_miles = 0.0

    for day in days:
        for seg in day["segments"]:
            if seg["type"] == "DRIVE":
                cumulative_miles += seg["miles_this_segment"]
                continue
            if seg["type"] == "OFF_DUTY":
                continue  # day-boundary padding, not a real stop

            lat, lon = routing.point_at_distance(polyline, cumulative_miles)

            stops.append(
                {
                    "type": seg["type"],
                    "location": seg["location"],
                    "latitude": lat,
                    "longitude": lon,
                    "arrival_time": seg["start_time"],
                    "departure_time": seg["end_time"],
                    "hos_state": seg["hos_state"],
                }
            )

    return stops
