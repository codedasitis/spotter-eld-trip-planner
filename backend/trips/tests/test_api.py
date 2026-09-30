"""
trips/tests/test_api.py

Contract-level tests for the HTTP layer: status codes and error shapes,
not HOS math (that's test_hos_engine.py's job). Every external call
(geocoding, routing) is mocked -- these tests must pass with zero network
access, which is also exactly how they run in CI.
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from trips.geocoding import GeocodedLocation, GeocodingError


class HealthCheckTest(TestCase):
    def test_health_check_returns_ok_and_version(self):
        client = APIClient()
        response = client.get("/api/v1/trip/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok", "version": "1.0.0"})


class CycleExhaustionApiTest(TestCase):
    def test_cycle_used_ge_70_returns_422_with_specific_message_before_routing(self):
        client = APIClient()
        with patch("trips.views.geocode") as mock_geocode, patch("trips.routing.get_route") as mock_get_route:
            response = client.post(
                "/api/v1/trip/plan/",
                {
                    "current_location": "Chicago, IL",
                    "pickup_location": "St. Louis, MO",
                    "dropoff_location": "Nashville, TN",
                    "current_cycle_used": 70.0,
                },
                format="json",
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.data["current_cycle_used"],
            [
                "Driver has exhausted the 70-hour cycle. A 34-hour restart "
                "is required before this trip can begin."
            ],
        )
        # fails fast: no geocoding or routing call was ever made for a
        # trip that can never be planned
        mock_geocode.assert_not_called()
        mock_get_route.assert_not_called()


class LocationNotFoundApiTest(TestCase):
    def test_unresolvable_location_returns_422_with_field_error(self):
        client = APIClient()

        def fake_geocode(text):
            if text == "Zzzznotarealplace":
                raise GeocodingError("Location not found. Please enter a city and state.")
            return GeocodedLocation(text, 0.0, 0.0)

        with patch("trips.views.geocode", side_effect=fake_geocode):
            response = client.post(
                "/api/v1/trip/plan/",
                {
                    "current_location": "Chicago, IL",
                    "pickup_location": "Zzzznotarealplace",
                    "dropoff_location": "Nashville, TN",
                    "current_cycle_used": 14.5,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.data["pickup_location"], ["Location not found. Please enter a city and state."]
        )


class HappyPathApiTest(TestCase):
    def test_valid_request_returns_full_plan_matching_assessment_example(self):
        client = APIClient()
        fixed = {
            "Chicago, IL": GeocodedLocation("Chicago, IL, USA", 41.8781, -87.6298),
            "St. Louis, MO": GeocodedLocation("St. Louis, MO, USA", 38.6270, -90.1994),
            "Nashville, TN": GeocodedLocation("Nashville, TN, USA", 36.1627, -86.7816),
        }
        with patch("trips.views.geocode", side_effect=lambda t: fixed[t]):
            response = client.post(
                "/api/v1/trip/plan/",
                {
                    "current_location": "Chicago, IL",
                    "pickup_location": "St. Louis, MO",
                    "dropoff_location": "Nashville, TN",
                    "current_cycle_used": 14.5,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.data
        for key in (
            "trip_id",
            "total_distance_miles",
            "total_driving_hours",
            "total_trip_hours",
            "routing_source",
            "days",
            "log_sheets",
            "stops",
        ):
            self.assertIn(key, body)

        self.assertIn(body["routing_source"], ("osrm", "haversine_fallback"))
        self.assertGreater(len(body["days"]), 0)
        self.assertEqual(len(body["days"]), len(body["log_sheets"]))

        # These use datetime.now() as the plan's start time (the
        # assessment gives no explicit departure timestamp), so which day
        # index things land on depends on the wall clock when the test
        # runs -- search across all days rather than assuming day 0.
        all_segments = [s for day in body["days"] for s in day["segments"]]
        pickup_segments = [s for s in all_segments if s["type"] == "PICKUP"]
        dropoff_segments = [s for s in all_segments if s["type"] == "DROPOFF"]
        self.assertEqual(len(pickup_segments), 1)
        self.assertEqual(len(dropoff_segments), 1)
        self.assertIn("Pickup", pickup_segments[0]["remark"])
        self.assertIn("Drop-off", dropoff_segments[0]["remark"])
