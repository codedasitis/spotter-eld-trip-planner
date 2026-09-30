"""
trips/serializers.py

DRF serializers. These only validate shape and bounds -- they never
contain HOS business logic (that lives entirely in hos_engine.TripPlanner).
"""

from rest_framework import serializers


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=200, allow_blank=False)
    pickup_location = serializers.CharField(max_length=200, allow_blank=False)
    dropoff_location = serializers.CharField(max_length=200, allow_blank=False)
    # This is a sanity bound only (rejects garbage like -5 or 10000), not
    # the business rule. The real "70-hour cycle" boundary is owned
    # entirely by TripPlanner.validate_cycle_hours -- duplicating it here
    # with a hard max_value=70 would silently swallow the exhausted-cycle
    # case behind a generic DRF error instead of the engine's specific
    # "34-hour restart required" message.
    current_cycle_used = serializers.FloatField(min_value=0.0, max_value=200.0)


# --- response-shape serializers (used for documentation / consistent
# output shape; the engine already returns plain dicts matching this
# shape, so these are declared for clarity and OpenAPI-style
# introspection rather than as a runtime validation gate on our own data).

class HOSStateSerializer(serializers.Serializer):
    cycle_hours_used = serializers.FloatField()
    driving_hours_today = serializers.FloatField()
    on_duty_hours_today = serializers.FloatField()
    hours_since_last_break = serializers.FloatField()
    window_opened_at = serializers.CharField(allow_null=True)


class SegmentSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    duty_status = serializers.CharField()
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    duration_hours = serializers.FloatField()
    location = serializers.CharField()
    remark = serializers.CharField()
    is_stationary = serializers.BooleanField()
    miles_this_segment = serializers.FloatField()
    day_index = serializers.IntegerField()
    hos_state = HOSStateSerializer()


class DayTotalsSerializer(serializers.Serializer):
    off_duty_hours = serializers.FloatField()
    sleeper_hours = serializers.FloatField()
    driving_hours = serializers.FloatField()
    on_duty_not_driving_hours = serializers.FloatField()
    total_miles = serializers.FloatField()


class DaySerializer(serializers.Serializer):
    day_index = serializers.IntegerField()
    date = serializers.CharField()
    segments = SegmentSerializer(many=True)
    totals = DayTotalsSerializer()


class DriverInfoSerializer(serializers.Serializer):
    tractor_number = serializers.CharField()
    trailer_number = serializers.CharField()
    home_terminal = serializers.CharField()
    shipper = serializers.CharField()
    commodity = serializers.CharField()
    total_miles = serializers.FloatField()


class RemarkSerializer(serializers.Serializer):
    time = serializers.CharField()
    location = serializers.CharField()
    activity = serializers.CharField()


class DailyTotalsSerializer(serializers.Serializer):
    line_1_hours = serializers.FloatField()
    line_2_hours = serializers.FloatField()
    line_3_hours = serializers.FloatField()
    line_4_hours = serializers.FloatField()
    total_on_duty_hours = serializers.FloatField()


class LogSheetSerializer(serializers.Serializer):
    day_index = serializers.IntegerField()
    date = serializers.CharField()
    driver_info = DriverInfoSerializer()
    grid_segments = SegmentSerializer(many=True)
    remarks = RemarkSerializer(many=True)
    daily_totals = DailyTotalsSerializer()


class StopMarkerSerializer(serializers.Serializer):
    type = serializers.CharField()
    location = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    arrival_time = serializers.CharField()
    departure_time = serializers.CharField()
    hos_state = HOSStateSerializer()


class TripPlanResponseSerializer(serializers.Serializer):
    trip_id = serializers.CharField()
    total_distance_miles = serializers.FloatField()
    total_driving_hours = serializers.FloatField()
    total_trip_hours = serializers.FloatField()
    routing_source = serializers.CharField()
    route_geometry = serializers.ListField(child=serializers.ListField(), allow_null=True)
    stops = StopMarkerSerializer(many=True)
    days = DaySerializer(many=True)
    log_sheets = LogSheetSerializer(many=True)
