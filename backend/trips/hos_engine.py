"""
trips/hos_engine.py

Pure-Python Hours-of-Service (HOS) trip planning engine.

No Django imports, no ORM, no network I/O. This module is deliberately
isolated so it can be unit tested (see tests/test_hos_engine.py) without
Django running at all, and so the exact object the API serializes is the
exact object the tests exercise directly. If a rule is wrong, it is wrong
here -- nowhere else in the codebase re-implements HOS math.

Scope, per the assessment brief:
    - Property-carrying driver
    - 70-hour / 8-day cycle (no 60/7 option -- brief doesn't ask for it)
    - No adverse driving conditions exception
    - Fuel at least once every 1,000 miles
    - 1 hour each for pickup and drop-off

Rolling-window simplification
------------------------------
The brief supplies a single scalar, `current_cycle_used`, rather than
eight days of prior duty history. A true rolling 8-day window needs that
history (hours "roll off" day by day). Without it, this engine treats
cycle usage as a running total that only ever *increases* as the planned
trip consumes on-duty hours, and can only be brought back to zero by a
34-consecutive-hour restart. That is a conservative simplification: it
will never *under*-report how much cycle a driver has used, which is the
safe direction to be wrong in for a compliance tool. This is called out
explicitly rather than silently assumed.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Constants. Every magic number in the ruleset lives here, named, so it can
# be audited against 49 CFR 395 without hunting through control flow.
# ---------------------------------------------------------------------------

MAX_DRIVING_HOURS = 11.0                     # 11-hour driving limit
MAX_WINDOW_HOURS = 14.0                      # 14-hour on-duty window
BREAK_REQUIRED_AFTER_DRIVING_HOURS = 8.0     # 30-min break after 8h driving
REQUIRED_BREAK_HOURS = 0.5
MIN_OFF_DUTY_RESET_HOURS = 10.0              # 10 consecutive hours off duty
RESTART_HOURS = 34.0                         # 34-hour restart
MAX_CYCLE_HOURS = 70.0                       # 70-hour / 8-day cap

FUEL_INTERVAL_MILES = 1000.0
FUEL_STOP_HOURS = 0.5

PICKUP_DURATION_HOURS = 1.0
DROPOFF_DURATION_HOURS = 1.0

# Used only when a leg has no routed duration attached (defensive default;
# in normal operation every leg comes from OSRM or the haversine fallback,
# both of which always supply a duration).
ASSUMED_AVERAGE_SPEED_MPH = 55.0

FLOAT_EPSILON = 1e-6


class HOSViolationError(Exception):
    """
    Raised when a trip cannot be planned at all under HOS rules -- as
    opposed to a mid-trip constraint, which the engine resolves by
    inserting a rest/restart segment rather than raising.
    """


def _round_preserving_sum(values: dict, decimals: int = 2) -> dict:
    """
    Round every value in `values` to `decimals` places such that the
    rounded values still sum to the (separately rounded) total.

    Rounding each of the four duty-status totals independently can make
    numbers that truly sum to 24.0 hours display as 23.99 or 24.01 --
    for a compliance log where "the day sums to 24 hours" is the whole
    point, that is not an acceptable rounding artifact. This uses the
    largest-remainder method: round every value down, then hand out the
    leftover hundredths to whichever values were closest to rounding up.
    """
    scale = 10**decimals
    raw_total = sum(values.values())
    target_units = round(raw_total * scale)

    floor_units = {k: math.floor(v * scale + 1e-9) for k, v in values.items()}
    remainders = {k: (v * scale) - floor_units[k] for k, v in values.items()}

    leftover_units = max(0, target_units - sum(floor_units.values()))
    ordered_keys = sorted(values.keys(), key=lambda k: remainders[k], reverse=True)

    result_units = dict(floor_units)
    for key in ordered_keys[:leftover_units]:
        result_units[key] += 1

    return {k: result_units[k] / scale for k in values}


class SegmentType(str, Enum):
    DRIVE = "DRIVE"
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    BREAK = "BREAK"                # mandatory 30-minute break
    REST = "REST"                  # 10-hour off-duty reset
    FUEL = "FUEL"                  # standalone fuel stop
    REST_AND_FUEL = "REST_AND_FUEL"  # fuel threshold merged into a 10-hr reset
    RESTART_34 = "RESTART_34"      # 34-hour cycle restart
    OFF_DUTY = "OFF_DUTY"          # day-boundary padding (before/after trip)

    # `REST_AND_FUEL`, `BREAK`, `RESTART_34`, and `OFF_DUTY` extend the
    # abridged type list in the assessment brief. They exist because
    # collapsing them into "REST" or "FUEL" would mislabel what actually
    # happened on a real log -- a merged fuel-and-rest stop is not the same
    # remark as a plain rest, and a 34-hour restart is not the same legal
    # event as a 10-hour reset.


class DutyStatus(str, Enum):
    OFF_DUTY = "LINE_1_OFF_DUTY"
    SLEEPER_BERTH = "LINE_2_SLEEPER_BERTH"
    DRIVING = "LINE_3_DRIVING"
    ON_DUTY_NOT_DRIVING = "LINE_4_ON_DUTY_NOT_DRIVING"


@dataclass(frozen=True)
class HOSState:
    """A snapshot of the driver's HOS clocks at one instant."""

    cycle_hours_used: float
    hours_since_last_break: float
    window_opened_at: Optional[datetime]
    # Filled in during the day-grouping pass (see TripPlanner._finalize),
    # because these two are calendar-day scoped and the simulation loop
    # above works in window-scoped time, not calendar days.
    driving_hours_today: float = 0.0
    on_duty_hours_today: float = 0.0

    def as_dict(self) -> dict:
        return {
            "cycle_hours_used": round(self.cycle_hours_used, 2),
            "driving_hours_today": round(self.driving_hours_today, 2),
            "on_duty_hours_today": round(self.on_duty_hours_today, 2),
            "hours_since_last_break": round(self.hours_since_last_break, 2),
            "window_opened_at": (
                self.window_opened_at.strftime("%H:%M") if self.window_opened_at else None
            ),
        }


@dataclass
class Segment:
    type: SegmentType
    duty_status: DutyStatus
    start_dt: datetime
    end_dt: datetime
    location: str
    remark: str
    is_stationary: bool
    miles_this_segment: float
    hos_state_before: HOSState
    hos_state_after: HOSState
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def duration_hours(self) -> float:
        return (self.end_dt - self.start_dt).total_seconds() / 3600.0

    def format_end_time(self) -> str:
        """Render '24:00' instead of '00:00' when a segment ends exactly at
        the day boundary -- this is standard ELD-log notation and avoids a
        segment that visually appears to end before it starts."""
        if self.end_dt.time() == datetime.min.time() and self.end_dt > self.start_dt:
            return "24:00"
        return self.end_dt.strftime("%H:%M")

    def to_dict(self, day_index: int) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "duty_status": self.duty_status.value,
            "start_time": self.start_dt.strftime("%H:%M"),
            "end_time": self.format_end_time(),
            "duration_hours": round(self.duration_hours, 2),
            "location": self.location,
            "remark": self.remark,
            "is_stationary": self.is_stationary,
            "miles_this_segment": round(self.miles_this_segment, 1),
            "day_index": day_index,
            "hos_state": self.hos_state_after.as_dict(),
        }


@dataclass
class TripLeg:
    """One point-to-point driving leg, as returned by the routing layer."""

    start_location: str
    end_location: str
    distance_miles: float
    duration_hours: float


@dataclass
class PlanResult:
    total_distance_miles: float
    total_driving_hours: float
    total_trip_hours: float
    days: list  # list[dict] -- see TripPlanner._finalize for shape
    log_sheets: list  # list[dict]


class TripPlanner:
    """
    Pure-Python HOS-compliant trip planner.

    >>> planner = TripPlanner(
    ...     current_location="Chicago, IL",
    ...     pickup_location="St. Louis, MO",
    ...     dropoff_location="Nashville, TN",
    ...     current_cycle_used=14.5,
    ...     legs=[leg_current_to_pickup, leg_pickup_to_dropoff],
    ...     start_datetime=datetime(2024, 1, 15, 8, 0),
    ... )
    >>> result = planner.plan()
    """

    def __init__(
        self,
        current_location: str,
        pickup_location: str,
        dropoff_location: str,
        current_cycle_used: float,
        legs: list,
        start_datetime: datetime,
        home_terminal: Optional[str] = None,
    ):
        self._validate_inputs(current_cycle_used, legs)

        self.current_location = current_location
        self.pickup_location = pickup_location
        self.dropoff_location = dropoff_location
        self.current_cycle_used = float(current_cycle_used)
        self.legs = legs
        self.start_datetime = start_datetime
        self.home_terminal = home_terminal or current_location

        # Mutable simulation state.
        self._segments: list[Segment] = []
        self._now = start_datetime
        self._cycle_hours_used = self.current_cycle_used
        self._driving_hours_in_window = 0.0
        self._hours_since_break = 0.0
        self._window_opened_at: Optional[datetime] = None
        self._miles_since_fuel = 0.0

    # -- validation ---------------------------------------------------

    @staticmethod
    def validate_cycle_hours(current_cycle_used) -> None:
        """
        Exposed as a standalone check (not just folded into __init__) so
        the API layer can reject an exhausted cycle *before* spending a
        geocoding or routing call on a trip that can never be planned --
        without re-implementing the "70 hours" rule a second time outside
        this class. This is the one and only place that number lives.
        """
        if not isinstance(current_cycle_used, (int, float)) or isinstance(current_cycle_used, bool):
            raise HOSViolationError("current_cycle_used must be a number.")
        if current_cycle_used < 0.0:
            raise HOSViolationError("current_cycle_used cannot be negative.")
        if current_cycle_used >= MAX_CYCLE_HOURS:
            raise HOSViolationError(
                "Driver has exhausted the 70-hour cycle. A 34-hour restart "
                "is required before this trip can begin."
            )

    @staticmethod
    def _validate_inputs(current_cycle_used, legs) -> None:
        TripPlanner.validate_cycle_hours(current_cycle_used)
        if not legs:
            raise HOSViolationError("At least one driving leg is required to plan a trip.")

    # -- public API -----------------------------------------------------

    def plan(self) -> PlanResult:
        self._drive_leg(self.legs[0], destination_label=self.pickup_location)
        self._stationary_on_duty_stop(
            type_=SegmentType.PICKUP,
            duration_hours=PICKUP_DURATION_HOURS,
            location=self.pickup_location,
            remark="Pickup + pre-trip inspection",
        )

        self._drive_leg(self.legs[1], destination_label=self.dropoff_location)
        self._stationary_on_duty_stop(
            type_=SegmentType.DROPOFF,
            duration_hours=DROPOFF_DURATION_HOURS,
            location=self.dropoff_location,
            remark="Drop-off + post-trip inspection",
        )

        total_miles = sum(leg.distance_miles for leg in self.legs)
        return self._finalize(total_miles)

    # -- driving loop -----------------------------------------------------

    def _drive_leg(self, leg: TripLeg, destination_label: str) -> None:
        remaining_hours = leg.duration_hours
        if remaining_hours <= FLOAT_EPSILON:
            return
        speed_mph = (
            leg.distance_miles / leg.duration_hours
            if leg.duration_hours > FLOAT_EPSILON
            else ASSUMED_AVERAGE_SPEED_MPH
        )

        while remaining_hours > FLOAT_EPSILON:
            if self._window_opened_at is None:
                self._window_opened_at = self._now

            room_in_11hr = MAX_DRIVING_HOURS - self._driving_hours_in_window
            room_in_window = MAX_WINDOW_HOURS - self._elapsed_window_hours()
            room_before_break = BREAK_REQUIRED_AFTER_DRIVING_HOURS - self._hours_since_break
            room_before_cycle_cap = MAX_CYCLE_HOURS - self._cycle_hours_used
            room_before_fuel_miles = FUEL_INTERVAL_MILES - self._miles_since_fuel
            room_before_fuel_hours = (
                room_before_fuel_miles / speed_mph if speed_mph > FLOAT_EPSILON else float("inf")
            )

            drive_chunk_hours = max(
                0.0,
                min(
                    remaining_hours,
                    room_in_11hr,
                    room_in_window,
                    room_before_break,
                    room_before_cycle_cap,
                    room_before_fuel_hours,
                ),
            )

            if drive_chunk_hours > FLOAT_EPSILON:
                self._append_drive_chunk(drive_chunk_hours, speed_mph, destination_label)
                remaining_hours -= drive_chunk_hours

            if remaining_hours <= FLOAT_EPSILON:
                break

            self._resolve_binding_constraint(
                room_in_11hr=room_in_11hr - drive_chunk_hours,
                room_in_window=room_in_window - drive_chunk_hours,
                room_before_break=room_before_break - drive_chunk_hours,
                room_before_cycle_cap=room_before_cycle_cap - drive_chunk_hours,
                room_before_fuel_hours=room_before_fuel_hours - drive_chunk_hours,
                # `_resolve_binding_constraint` is only ever reached when
                # `remaining_hours` is still > 0, i.e. the leg has NOT
                # finished yet -- every stop inserted from here is
                # therefore somewhere along the route, never at the
                # destination itself. Label it the same way the DRIVE
                # segments already are, or a mid-leg restart can end up
                # saying "at St. Louis" after the driver has gone all of
                # one hour from Chicago.
                location=f"En route to {destination_label}",
            )

    def _elapsed_window_hours(self) -> float:
        if self._window_opened_at is None:
            return 0.0
        return (self._now - self._window_opened_at).total_seconds() / 3600.0

    def _resolve_binding_constraint(
        self,
        *,
        room_in_11hr: float,
        room_in_window: float,
        room_before_break: float,
        room_before_cycle_cap: float,
        room_before_fuel_hours: float,
        location: str,
    ) -> None:
        """
        Exactly one (or more, if coincident) of these quantities is ~0,
        because `drive_chunk_hours` above was computed as the min of all
        five. Resolve in order of legal precedence:

        1. Cycle cap (70 hrs) -- only a 34-hour restart fixes this. This
           is the "cycle exhaustion mid-trip" edge case: the check is
           re-evaluated on every loop iteration, not only at the start of
           the trip.
        2. 14-hour window closed / 11-hour driving limit reached -- both
           require a 10-hour reset. This is the "window closes before the
           driving limit" edge case: either condition alone triggers the
           same resolution.
        3. Fuel due -- if a mandatory rest (case 1 or 2) isn't *also*
           triggering, a fuel stop alone is 30 minutes on duty, and (being
           >= the minimum break length) it also satisfies any pending
           break requirement, so break is folded into this branch too.
        4. Break due (fuel not due) -- a plain 30-minute break.
        """
        cycle_binding = room_before_cycle_cap <= FLOAT_EPSILON
        window_binding = room_in_window <= FLOAT_EPSILON
        driving_limit_binding = room_in_11hr <= FLOAT_EPSILON
        fuel_binding = room_before_fuel_hours <= FLOAT_EPSILON
        break_binding = room_before_break <= FLOAT_EPSILON

        if cycle_binding:
            self._insert_restart(location, also_fuel=fuel_binding)
        elif window_binding or driving_limit_binding:
            self._insert_reset(location, also_fuel=fuel_binding)
        elif fuel_binding:
            self._insert_fuel_stop(location)
        elif break_binding:
            self._insert_break(location)
        else:  # pragma: no cover - defensive; see docstring above
            raise AssertionError(
                "No binding HOS constraint found -- this indicates an engine bug, "
                "since drive_chunk_hours was computed as the min of these five values."
            )

    # -- segment builders -----------------------------------------------------

    def _snapshot(self) -> HOSState:
        return HOSState(
            cycle_hours_used=self._cycle_hours_used,
            hours_since_last_break=self._hours_since_break,
            window_opened_at=self._window_opened_at,
        )

    def _append_drive_chunk(self, hours: float, speed_mph: float, destination_label: str) -> None:
        before = self._snapshot()
        miles = hours * speed_mph
        start, end = self._now, self._now + timedelta(hours=hours)

        self._driving_hours_in_window += hours
        self._hours_since_break += hours
        self._cycle_hours_used += hours
        self._miles_since_fuel += miles
        self._now = end

        self._segments.append(
            Segment(
                type=SegmentType.DRIVE,
                duty_status=DutyStatus.DRIVING,
                start_dt=start,
                end_dt=end,
                location=f"En route to {destination_label}",
                remark="Driving",
                is_stationary=False,
                miles_this_segment=miles,
                hos_state_before=before,
                hos_state_after=self._snapshot(),
            )
        )

    def _stationary_on_duty_stop(self, type_: SegmentType, duration_hours: float, location: str, remark: str) -> None:
        if self._window_opened_at is None:
            self._window_opened_at = self._now
        before = self._snapshot()
        start, end = self._now, self._now + timedelta(hours=duration_hours)

        self._cycle_hours_used += duration_hours
        if duration_hours >= REQUIRED_BREAK_HOURS - FLOAT_EPSILON:
            self._hours_since_break = 0.0
        self._now = end

        self._segments.append(
            Segment(
                type=type_,
                duty_status=DutyStatus.ON_DUTY_NOT_DRIVING,
                start_dt=start,
                end_dt=end,
                location=location,
                remark=remark,
                is_stationary=True,
                miles_this_segment=0.0,
                hos_state_before=before,
                hos_state_after=self._snapshot(),
            )
        )

    def _insert_reset(self, location: str, also_fuel: bool = False) -> None:
        before = self._snapshot()
        start, end = self._now, self._now + timedelta(hours=MIN_OFF_DUTY_RESET_HOURS)

        self._driving_hours_in_window = 0.0
        self._hours_since_break = 0.0
        self._window_opened_at = None
        if also_fuel:
            self._miles_since_fuel = 0.0
        self._now = end

        type_ = SegmentType.REST_AND_FUEL if also_fuel else SegmentType.REST
        remark = "Rest + Fuel (10-hour reset)" if also_fuel else "10-hour off-duty reset"
        self._segments.append(
            Segment(
                type=type_,
                duty_status=DutyStatus.OFF_DUTY,
                start_dt=start,
                end_dt=end,
                location=location,
                remark=remark,
                is_stationary=True,
                miles_this_segment=0.0,
                hos_state_before=before,
                hos_state_after=self._snapshot(),
            )
        )

    def _insert_restart(self, location: str, also_fuel: bool = False) -> None:
        before = self._snapshot()
        start, end = self._now, self._now + timedelta(hours=RESTART_HOURS)

        self._cycle_hours_used = 0.0
        self._driving_hours_in_window = 0.0
        self._hours_since_break = 0.0
        self._window_opened_at = None
        if also_fuel:
            self._miles_since_fuel = 0.0
        self._now = end

        remark = "34-hour restart (cycle reset)" + (" + fuel" if also_fuel else "")
        self._segments.append(
            Segment(
                type=SegmentType.RESTART_34,
                duty_status=DutyStatus.OFF_DUTY,
                start_dt=start,
                end_dt=end,
                location=location,
                remark=remark,
                is_stationary=True,
                miles_this_segment=0.0,
                hos_state_before=before,
                hos_state_after=self._snapshot(),
            )
        )

    def _insert_fuel_stop(self, location: str) -> None:
        before = self._snapshot()
        start, end = self._now, self._now + timedelta(hours=FUEL_STOP_HOURS)

        self._miles_since_fuel = 0.0
        self._cycle_hours_used += FUEL_STOP_HOURS
        self._hours_since_break = 0.0  # a fuel stop is >= the minimum break length
        self._now = end

        self._segments.append(
            Segment(
                type=SegmentType.FUEL,
                duty_status=DutyStatus.ON_DUTY_NOT_DRIVING,
                start_dt=start,
                end_dt=end,
                location=location,
                remark="Fuel stop",
                is_stationary=True,
                miles_this_segment=0.0,
                hos_state_before=before,
                hos_state_after=self._snapshot(),
            )
        )

    def _insert_break(self, location: str) -> None:
        before = self._snapshot()
        start, end = self._now, self._now + timedelta(hours=REQUIRED_BREAK_HOURS)

        self._hours_since_break = 0.0
        self._now = end

        self._segments.append(
            Segment(
                type=SegmentType.BREAK,
                duty_status=DutyStatus.OFF_DUTY,
                start_dt=start,
                end_dt=end,
                location=location,
                remark="Mandatory 30-minute break",
                is_stationary=True,
                miles_this_segment=0.0,
                hos_state_before=before,
                hos_state_after=self._snapshot(),
            )
        )

    # -- finalization: midnight-splitting, day grouping, totals -----------

    def _finalize(self, total_miles: float) -> PlanResult:
        split_segments = self._split_across_midnight(self._segments)
        padded_segments = self._pad_day_boundaries(split_segments)
        days, log_sheets = self._group_by_day(padded_segments)

        total_driving_hours = sum(
            s.duration_hours for day in days for s in day["_segment_objs"] if s.type == SegmentType.DRIVE
        )
        total_trip_hours = (self._now - self.start_datetime).total_seconds() / 3600.0

        for day in days:
            del day["_segment_objs"]

        return PlanResult(
            total_distance_miles=round(total_miles, 1),
            total_driving_hours=round(total_driving_hours, 2),
            total_trip_hours=round(total_trip_hours, 2),
            days=days,
            log_sheets=log_sheets,
        )

    @staticmethod
    def _split_across_midnight(segments: list[Segment]) -> list[Segment]:
        """
        No segment in the final output is allowed to cross a calendar-day
        boundary (the SVG renderer assumes one 24-hour sheet per segment).
        Split any that do. Mileage and the interpolated HOS state are
        divided proportionally to the wall-clock share of each piece.
        """
        result: list[Segment] = []
        for seg in segments:
            total_seconds = (seg.end_dt - seg.start_dt).total_seconds()
            if total_seconds <= 0:
                result.append(seg)
                continue

            cursor = seg.start_dt
            remaining_miles = seg.miles_this_segment
            pieces: list[tuple[datetime, datetime]] = []
            while cursor.date() != seg.end_dt.date():
                midnight = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time())
                pieces.append((cursor, midnight))
                cursor = midnight
            pieces.append((cursor, seg.end_dt))

            for i, (piece_start, piece_end) in enumerate(pieces):
                fraction = (piece_end - piece_start).total_seconds() / total_seconds
                is_last = i == len(pieces) - 1
                piece_miles = seg.miles_this_segment * fraction if not seg.is_stationary else 0.0

                if is_last:
                    state_after = seg.hos_state_after
                elif not seg.is_stationary:
                    # DRIVE segments accrue cycle hours continuously, so a
                    # linear interpolation weighted by elapsed wall-clock
                    # fraction is exact here, not an approximation.
                    elapsed_fraction = (piece_end - seg.start_dt).total_seconds() / total_seconds
                    state_after = HOSState(
                        cycle_hours_used=seg.hos_state_before.cycle_hours_used
                        + elapsed_fraction
                        * (seg.hos_state_after.cycle_hours_used - seg.hos_state_before.cycle_hours_used),
                        hours_since_last_break=seg.hos_state_before.hours_since_last_break
                        + elapsed_fraction
                        * (
                            seg.hos_state_after.hours_since_last_break
                            - seg.hos_state_before.hours_since_last_break
                        ),
                        window_opened_at=seg.hos_state_before.window_opened_at,
                    )
                else:
                    # Stationary events (rest, restart, fuel, pickup,
                    # dropoff, break) change the driver's clocks atomically
                    # at the moment the event *completes*, not continuously
                    # while it's in progress. A rest period sitting at
                    # cycle=70 does not drift down to 58 partway through --
                    # it stays frozen at 70 until the reset actually lands
                    # on the final piece. Interpolating this one linearly
                    # would print a physically meaningless number.
                    state_after = seg.hos_state_before

                result.append(
                    replace(
                        seg,
                        id=str(uuid.uuid4()),
                        start_dt=piece_start,
                        end_dt=piece_end,
                        miles_this_segment=piece_miles,
                        hos_state_after=state_after,
                    )
                )
        return result

    def _pad_day_boundaries(self, segments: list[Segment]) -> list[Segment]:
        """
        Every calendar day touched by the trip must be represented by a
        full 24-hour log sheet. Pad the gap before the first segment of the
        trip's first day, and the gap after the last segment of every day,
        with OFF_DUTY -- this is what makes daily totals sum to exactly
        24.0 hours for every day, including a day that starts mid-morning
        because the driver departed at, say, 08:00.

        Padding is always a period of NOT moving, so it must be labeled
        with wherever the driver last actually was, never wherever a
        later segment is headed -- otherwise the gap before the trip
        even starts can end up reading "En route to St. Louis" before a
        single mile has been driven.
        """
        if not segments:
            return segments

        first_day = segments[0].start_dt.date()
        last_day = segments[-1].end_dt.date()
        padded: list[Segment] = []

        day = first_day
        seg_iter = iter(segments)
        pending = next(seg_iter, None)
        last_known_location = self.home_terminal

        while day <= last_day:
            day_start = datetime.combine(day, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            cursor = day_start

            todays_segments = []
            while pending is not None and pending.start_dt.date() == day:
                todays_segments.append(pending)
                pending = next(seg_iter, None)

            for seg in todays_segments:
                if seg.start_dt > cursor:
                    padded.append(self._off_duty_filler(cursor, seg.start_dt, last_known_location))
                padded.append(seg)
                cursor = seg.end_dt
                last_known_location = seg.location

            if cursor < day_end:
                padded.append(self._off_duty_filler(cursor, day_end, last_known_location))

            day += timedelta(days=1)

        return padded

    @staticmethod
    def _off_duty_filler(start: datetime, end: datetime, location: str) -> Segment:
        state = HOSState(cycle_hours_used=0.0, hours_since_last_break=0.0, window_opened_at=None)
        return Segment(
            type=SegmentType.OFF_DUTY,
            duty_status=DutyStatus.OFF_DUTY,
            start_dt=start,
            end_dt=end,
            location=location,
            remark="Off duty",
            is_stationary=True,
            miles_this_segment=0.0,
            hos_state_before=state,
            hos_state_after=state,
        )

    def _group_by_day(self, segments: list[Segment]) -> tuple[list, list]:
        first_day = segments[0].start_dt.date() if segments else self.start_datetime.date()

        by_day: dict[int, list[Segment]] = {}
        for seg in segments:
            day_index = (seg.start_dt.date() - first_day).days
            by_day.setdefault(day_index, []).append(seg)

        # carry the running "hos_state_before" fix-ups: the OFF_DUTY filler
        # segments above are constructed without a real cycle snapshot (they
        # don't change any clock), so backfill day-scoped driving/on-duty
        # totals in a single forward pass across the whole trip.
        driving_today = 0.0
        on_duty_today = 0.0
        current_day_index = 0

        days_out = []
        log_sheets_out = []

        for day_index in sorted(by_day.keys()):
            if day_index != current_day_index:
                driving_today = 0.0
                on_duty_today = 0.0
                current_day_index = day_index

            day_segments = by_day[day_index]
            day_date = first_day + timedelta(days=day_index)

            seg_dicts = []
            remarks = []
            totals = {
                "off_duty_hours": 0.0,
                "sleeper_hours": 0.0,
                "driving_hours": 0.0,
                "on_duty_not_driving_hours": 0.0,
                "total_miles": 0.0,
            }
            grid_segments = []

            for seg in day_segments:
                if seg.duty_status == DutyStatus.DRIVING:
                    driving_today += seg.duration_hours
                    on_duty_today += seg.duration_hours
                elif seg.duty_status == DutyStatus.ON_DUTY_NOT_DRIVING:
                    on_duty_today += seg.duration_hours

                enriched_state = replace(
                    seg.hos_state_after,
                    driving_hours_today=driving_today,
                    on_duty_hours_today=on_duty_today,
                )
                seg.hos_state_after = enriched_state

                d = seg.to_dict(day_index)
                seg_dicts.append(d)
                grid_segments.append(d)

                if seg.type not in (SegmentType.OFF_DUTY,) or seg is day_segments[0]:
                    if seg.type != SegmentType.OFF_DUTY:
                        remarks.append(
                            {
                                "time": d["start_time"],
                                "location": seg.location,
                                "activity": seg.remark,
                            }
                        )

                bucket = {
                    DutyStatus.OFF_DUTY: "off_duty_hours",
                    DutyStatus.SLEEPER_BERTH: "sleeper_hours",
                    DutyStatus.DRIVING: "driving_hours",
                    DutyStatus.ON_DUTY_NOT_DRIVING: "on_duty_not_driving_hours",
                }[seg.duty_status]
                totals[bucket] += seg.duration_hours
                totals["total_miles"] += seg.miles_this_segment

            duty_hour_keys = ("off_duty_hours", "sleeper_hours", "driving_hours", "on_duty_not_driving_hours")
            rounded_duty_hours = _round_preserving_sum({k: totals[k] for k in duty_hour_keys})
            totals = {**rounded_duty_hours, "total_miles": round(totals["total_miles"], 1)}

            days_out.append(
                {
                    "day_index": day_index,
                    "date": day_date.isoformat(),
                    "segments": seg_dicts,
                    "totals": totals,
                    "_segment_objs": day_segments,
                }
            )

            log_sheets_out.append(
                {
                    "day_index": day_index,
                    "date": day_date.isoformat(),
                    "driver_info": {
                        "tractor_number": "AUTO-001",
                        "trailer_number": "TRL-001",
                        "home_terminal": self.home_terminal,
                        "shipper": "Assessment Trip",
                        "commodity": "General Freight",
                        "total_miles": totals["total_miles"],
                    },
                    "grid_segments": grid_segments,
                    "remarks": remarks,
                    "daily_totals": {
                        "line_1_hours": totals["off_duty_hours"],
                        "line_2_hours": totals["sleeper_hours"],
                        "line_3_hours": totals["driving_hours"],
                        "line_4_hours": totals["on_duty_not_driving_hours"],
                        "total_on_duty_hours": round(
                            totals["driving_hours"] + totals["on_duty_not_driving_hours"], 2
                        ),
                    },
                }
            )

        return days_out, log_sheets_out
