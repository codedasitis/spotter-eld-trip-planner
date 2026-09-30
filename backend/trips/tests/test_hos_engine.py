"""
trips/tests/test_hos_engine.py

Behavioral tests only -- every assertion here checks a specific property
that would fail if the underlying logic were silently broken. None of
these assert `status_code == 200` or `len(segments) > 0` alone.
"""

from datetime import datetime
from unittest.mock import patch

import requests
from django.test import TestCase
from rest_framework.test import APIClient

from trips.geocoding import GeocodedLocation
from trips.hos_engine import (
    MAX_CYCLE_HOURS,
    HOSViolationError,
    SegmentType,
    TripLeg,
    TripPlanner,
)


def _make_leg(distance_miles: float, speed_mph: float = 55.0) -> TripLeg:
    return TripLeg(
        start_location="A",
        end_location="B",
        distance_miles=distance_miles,
        duration_hours=distance_miles / speed_mph,
    )


class ShortTripNoRestRequiredTest(TestCase):
    def test_short_trip_no_rest_required(self):
        """A 200-mile trip with a fresh cycle needs no rest at all, and the
        single day it occupies must still account for a full 24 hours."""
        planner = TripPlanner(
            current_location="Chicago, IL",
            pickup_location="Chicago, IL",
            dropoff_location="Springfield, IL",
            current_cycle_used=0.0,
            legs=[_make_leg(0), _make_leg(200)],
            start_datetime=datetime(2024, 1, 15, 8, 0),
        )
        result = planner.plan()

        self.assertEqual(len(result.days), 1)

        rest_types = {SegmentType.REST.value, SegmentType.REST_AND_FUEL.value, SegmentType.RESTART_34.value}
        segment_types = {s["type"] for s in result.days[0]["segments"]}
        self.assertEqual(
            segment_types & rest_types,
            set(),
            f"a 200-mile trip should never require a rest stop, got types: {segment_types}",
        )

        totals = result.days[0]["totals"]
        total_hours = sum(
            totals[k]
            for k in ("off_duty_hours", "sleeper_hours", "driving_hours", "on_duty_not_driving_hours")
        )
        self.assertAlmostEqual(total_hours, 24.0, places=4)


class CycleExhaustionTest(TestCase):
    def test_cycle_exhaustion_raises(self):
        """A driver who already reports 70+ hours used cannot be planned at
        all -- this must raise the specific HOSViolationError with the
        specific restart message, not a generic exception."""
        with self.assertRaises(HOSViolationError) as ctx:
            TripPlanner(
                current_location="Chicago, IL",
                pickup_location="St. Louis, MO",
                dropoff_location="Nashville, TN",
                current_cycle_used=70.0,
                legs=[_make_leg(300), _make_leg(300)],
                start_datetime=datetime(2024, 1, 15, 8, 0),
            )
        self.assertIn("34-hour restart is required", str(ctx.exception))

    def test_cycle_exhaustion_detected_mid_trip_not_only_at_start(self):
        """A driver starting well under 70 hours (60) but attempting a trip
        that would push them over must have a 34-hour restart inserted
        automatically partway through -- not just validated at t=0."""
        planner = TripPlanner(
            current_location="St. Louis, MO",
            pickup_location="St. Louis, MO",
            dropoff_location="Nashville, TN",
            current_cycle_used=60.0,
            legs=[_make_leg(0), _make_leg(900)],
            start_datetime=datetime(2024, 1, 15, 8, 0),
        )
        result = planner.plan()

        restart_segments = [
            s for day in result.days for s in day["segments"] if s["type"] == SegmentType.RESTART_34.value
        ]
        self.assertGreater(len(restart_segments), 0, "expected a 34-hour restart to be inserted mid-trip")

        # cycle usage must never be reported above the hard cap anywhere
        # in the output
        for day in result.days:
            for seg in day["segments"]:
                self.assertLessEqual(seg["hos_state"]["cycle_hours_used"], MAX_CYCLE_HOURS + 0.01)


class FuelRestMergeTest(TestCase):
    def test_fuel_stop_merged_into_rest(self):
        """If the 1,000-mile fuel threshold and the 11-hour driving limit
        land at the same instant *and there is still more driving left to
        do afterward*, the engine must emit exactly one merged
        REST_AND_FUEL segment -- never two adjacent stops with a
        zero-duration drive segment stitched between them.

        (The coincidence has to fall mid-leg, not at the very end of the
        trip: if the driving limit is reached exactly as the last mile is
        driven, there is nothing left to resume afterward, so no stop is
        required at all -- correctly. This leg is 1,200 miles at a speed
        that puts the fuel/driving-limit coincidence at mile 1,000 with
        200 miles still remaining.)
        """
        leg = TripLeg("Pickup", "Dropoff", distance_miles=1200.0, duration_hours=1200.0 / (1000.0 / 11.0))
        planner = TripPlanner(
            current_location="Pickup",
            pickup_location="Pickup",
            dropoff_location="Dropoff",
            current_cycle_used=0.0,
            legs=[_make_leg(0), leg],
            start_datetime=datetime(2024, 1, 15, 6, 0),
        )
        result = planner.plan()
        all_segments = [s for day in result.days for s in day["segments"]]

        # The merged stop is 10 hours long and may itself get split across
        # midnight (same rule as everywhere else: no segment crosses a day
        # boundary). Group consecutive same-type segments so a split merge
        # still counts as the single logical event it is.
        merge_start = next(i for i, s in enumerate(all_segments) if s["type"] == "REST_AND_FUEL")
        merge_end = merge_start
        while merge_end < len(all_segments) and all_segments[merge_end]["type"] == "REST_AND_FUEL":
            merge_end += 1
        merge_block = all_segments[merge_start:merge_end]

        self.assertAlmostEqual(sum(s["duration_hours"] for s in merge_block), 10.0, places=2)

        standalone_fuel = [s for s in all_segments if s["type"] == "FUEL"]
        self.assertEqual(standalone_fuel, [], "fuel should have been merged, not left standalone")

        # exactly one such merged block exists in the whole trip (not two
        # separate merge events)
        other_rest_and_fuel_after = [s for s in all_segments[merge_end:] if s["type"] == "REST_AND_FUEL"]
        self.assertEqual(other_rest_and_fuel_after, [])

        # driving resumes after the merged stop to finish the remaining miles
        driving_after = [s for s in all_segments[merge_end:] if s["type"] == "DRIVE"]
        self.assertGreater(len(driving_after), 0, "driving must resume after the merged rest+fuel stop")

        # no zero-duration DRIVE segment anywhere
        for s in all_segments:
            if s["type"] == "DRIVE":
                self.assertGreater(s["duration_hours"], 0.0)


class WindowClosesBeforeDrivingLimitTest(TestCase):
    def test_14_hour_window_closes_before_11_hour_drive(self):
        """If 4 hours of on-duty-not-driving time occur before driving
        starts, only 10 hours remain in the 14-hour window -- less than
        the 11-hour driving cap. The window must be what stops the driver
        (at 9.5 hours of actual driving, once a mandatory break is
        subtracted from that 10-hour budget), not the 11-hour limit, and
        driving must resume after the resulting 10-hour reset."""
        leg_stub = TripLeg("A", "A", distance_miles=0, duration_hours=0)
        long_leg = TripLeg("Pickup", "Dropoff", distance_miles=11 * 55, duration_hours=11)
        planner = TripPlanner(
            current_location="A",
            pickup_location="A",
            dropoff_location="Dropoff",
            current_cycle_used=0.0,
            legs=[leg_stub, long_leg],
            start_datetime=datetime(2024, 1, 15, 6, 0),
        )
        # Exercise the same primitive PICKUP/DROPOFF use internally -- this
        # is not test-only logic, it's the engine's own stationary-stop path.
        planner._stationary_on_duty_stop(
            type_=SegmentType.PICKUP, duration_hours=4.0, location="A", remark="Extended loading"
        )
        planner._drive_leg(long_leg, destination_label="Dropoff")
        result = planner._finalize(total_miles=long_leg.distance_miles)

        all_segments = [s for day in result.days for s in day["segments"]]
        first_reset_index = next(i for i, s in enumerate(all_segments) if s["type"] == "REST")
        driving_before_reset = sum(
            s["duration_hours"] for s in all_segments[:first_reset_index] if s["type"] == "DRIVE"
        )

        self.assertLess(driving_before_reset, 11.0, "the window should cut driving short of the 11-hour cap")
        self.assertAlmostEqual(driving_before_reset, 9.5, places=2)

        # The 10-hour reset itself gets split at midnight (no segment is
        # allowed to cross a day boundary -- see _split_across_midnight),
        # so it shows up as two consecutive REST pieces. Sum them back
        # together to check the reset's true total length.
        reset_pieces = []
        i = first_reset_index
        while i < len(all_segments) and all_segments[i]["type"] == "REST":
            reset_pieces.append(all_segments[i])
            i += 1
        total_reset_hours = sum(s["duration_hours"] for s in reset_pieces)
        self.assertAlmostEqual(total_reset_hours, 10.0, places=2)

        driving_after_reset = sum(s["duration_hours"] for s in all_segments[i:] if s["type"] == "DRIVE")
        self.assertGreater(driving_after_reset, 0.0, "driving must resume after the reset")
        self.assertAlmostEqual(driving_before_reset + driving_after_reset, 11.0, places=2)


class MultiDayTotalsTest(TestCase):
    def test_multi_day_trip_log_sheets_total_24_each_day(self):
        """A long trip spans several log sheets -- every single one of
        them must account for exactly 24 hours, including the first
        (which starts mid-morning) and the last (which ends mid-trip)."""
        planner = TripPlanner(
            current_location="Los Angeles, CA",
            pickup_location="Los Angeles, CA",
            dropoff_location="Chicago, IL",
            current_cycle_used=5.0,
            legs=[_make_leg(0), _make_leg(1500)],
            start_datetime=datetime(2024, 1, 15, 8, 0),
        )
        result = planner.plan()

        self.assertGreater(len(result.days), 1, "a 1,500-mile trip should span multiple days")

        for day in result.days:
            total = round(sum(day["totals"][k] for k in day["totals"] if k != "total_miles"), 4)
            self.assertEqual(total, 24.0, f"day {day['day_index']} totals do not sum to 24.0: {day['totals']}")

        for sheet in result.log_sheets:
            dt = sheet["daily_totals"]
            total = round(dt["line_1_hours"] + dt["line_2_hours"] + dt["line_3_hours"] + dt["line_4_hours"], 4)
            self.assertEqual(total, 24.0, f"log sheet {sheet['day_index']} daily_totals do not sum to 24.0")


class SegmentLocationLabelingTest(TestCase):
    def test_stop_forced_mid_leg_is_labeled_en_route_not_destination(self):
        """A stop forced by a constraint firing partway through a leg must
        be labeled as en route to the destination, never as though the
        driver had already arrived. Regression test for a bug where a
        34-hour restart triggered after just 1 hour of driving toward St.
        Louis (out of a ~5.5 hour leg) was labeled "St. Louis, MO", as if
        the driver were already there."""
        planner = TripPlanner(
            current_location="Chicago, IL",
            pickup_location="St. Louis, MO",
            dropoff_location="Nashville, TN",
            current_cycle_used=69.0,
            legs=[_make_leg(300), _make_leg(300)],
            start_datetime=datetime(2024, 1, 15, 8, 0),
        )
        result = planner.plan()
        all_segments = [s for day in result.days for s in day["segments"]]
        restart_segments = [s for s in all_segments if s["type"] == "RESTART_34"]

        self.assertGreater(len(restart_segments), 0, "expected the 70-hour cap to force a restart")
        for seg in restart_segments:
            self.assertTrue(
                seg["location"].startswith("En route to"),
                f"a mid-leg restart must say 'En route to ...', got: {seg['location']!r}",
            )
            self.assertNotEqual(seg["location"], "St. Louis, MO")


    def test_leading_padding_uses_start_location_not_upcoming_destination(self):
        """The off-duty gap before the trip even starts (e.g. 00:00-08:00
        on a driver departing at 08:00) must be labeled with where the
        driver actually starts, never with wherever their first drive is
        headed. Regression test for a bug where this padding read
        'En route to St. Louis, MO' before a single mile had been driven."""
        planner = TripPlanner(
            current_location="Chicago, IL",
            pickup_location="St. Louis, MO",
            dropoff_location="Nashville, TN",
            current_cycle_used=0.0,
            legs=[_make_leg(0), _make_leg(300)],
            start_datetime=datetime(2024, 1, 15, 8, 0),
        )
        result = planner.plan()
        leading_padding = result.days[0]["segments"][0]

        self.assertEqual(leading_padding["type"], "OFF_DUTY")
        self.assertEqual(leading_padding["location"], "Chicago, IL")


class DutyHourRoundingTest(TestCase):
    def test_daily_totals_sum_to_24_even_when_naive_per_bucket_rounding_would_not(self):
        """Regression test for the exact scenario that first surfaced this:
        rounding each of the four duty-hour buckets independently produced
        a day that displayed as summing to 23.99 instead of 24.0. This
        trip (a cycle nearly exhausted at the very start, forcing a
        34-hour restart one hour into the first leg) reproduces it."""
        leg0 = TripLeg("Chicago, IL", "St. Louis, MO", distance_miles=300, duration_hours=300 / 55)
        leg1 = TripLeg("St. Louis, MO", "Nashville, TN", distance_miles=300, duration_hours=300 / 55)
        planner = TripPlanner(
            current_location="Chicago, IL",
            pickup_location="St. Louis, MO",
            dropoff_location="Nashville, TN",
            current_cycle_used=69.0,
            legs=[leg0, leg1],
            start_datetime=datetime(2026, 9, 13, 8, 0),
        )
        result = planner.plan()

        for day in result.days:
            total = sum(day["totals"][k] for k in day["totals"] if k != "total_miles")
            self.assertEqual(
                round(total, 4), 24.0, f"day {day['day_index']} totals sum to {total}, not 24.0"
            )


class OsrmFallbackTest(TestCase):
    def test_osrm_timeout_falls_back_to_haversine(self):
        """When OSRM times out, the API must still return a full, valid
        trip plan -- just tagged as a haversine fallback instead of
        silently failing or silently pretending the estimate is live data."""
        client = APIClient()

        fixed_locations = {
            "Chicago, IL": GeocodedLocation("Chicago, IL, USA", 41.8781, -87.6298),
            "St. Louis, MO": GeocodedLocation("St. Louis, MO, USA", 38.6270, -90.1994),
            "Nashville, TN": GeocodedLocation("Nashville, TN, USA", 36.1627, -86.7816),
        }

        with patch("trips.views.geocode", side_effect=lambda text: fixed_locations[text]), patch(
            "trips.routing.requests.get", side_effect=requests.Timeout("simulated OSRM timeout")
        ):
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
        self.assertEqual(response.data["routing_source"], "haversine_fallback")
        self.assertGreater(len(response.data["days"]), 0)
        self.assertGreater(response.data["total_distance_miles"], 0)
