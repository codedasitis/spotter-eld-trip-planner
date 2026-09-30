// These types are a direct mirror of trips/serializers.py on the backend.
// If a field is renamed there, it must be renamed here -- there is no
// business logic in this file, only shape.

export type SegmentType =
  | "DRIVE"
  | "PICKUP"
  | "DROPOFF"
  | "BREAK"
  | "REST"
  | "FUEL"
  | "REST_AND_FUEL"
  | "RESTART_34"
  | "OFF_DUTY"
  // The two below are not emitted by this assessment's simplified engine
  // (see trips/hos_engine.py's module docstring on the rolling-window
  // simplification) but are part of the full ELD vocabulary and are
  // exercised by the DailyLogSheet renderer test fixture, which is
  // hand-authored from real log-book data rather than engine output.
  | "SLEEPER"
  | "ON_DUTY";

export type DutyStatus =
  | "LINE_1_OFF_DUTY"
  | "LINE_2_SLEEPER_BERTH"
  | "LINE_3_DRIVING"
  | "LINE_4_ON_DUTY_NOT_DRIVING";

export interface HOSState {
  cycle_hours_used: number;
  driving_hours_today: number;
  on_duty_hours_today: number;
  hours_since_last_break: number;
  window_opened_at: string | null;
}

export interface Segment {
  id: string;
  type: SegmentType;
  duty_status: DutyStatus;
  start_time: string;
  end_time: string;
  duration_hours: number;
  location: string;
  remark: string;
  is_stationary: boolean;
  miles_this_segment: number;
  day_index: number;
  hos_state: HOSState;
}

export interface DayTotals {
  off_duty_hours: number;
  sleeper_hours: number;
  driving_hours: number;
  on_duty_not_driving_hours: number;
  total_miles: number;
}

export interface TripDay {
  day_index: number;
  date: string;
  segments: Segment[];
  totals: DayTotals;
}

export interface DriverInfo {
  tractor_number: string;
  trailer_number: string;
  home_terminal: string;
  shipper: string;
  commodity: string;
  total_miles: number;
}

export interface Remark {
  time: string;
  location: string;
  activity: string;
}

export interface DailyTotals {
  line_1_hours: number;
  line_2_hours: number;
  line_3_hours: number;
  line_4_hours: number;
  total_on_duty_hours: number;
}

export interface LogSheet {
  day_index: number;
  date: string;
  driver_info: DriverInfo;
  grid_segments: Segment[];
  remarks: Remark[];
  daily_totals: DailyTotals;
}

export interface StopMarker {
  type: SegmentType;
  location: string;
  latitude: number;
  longitude: number;
  arrival_time: string;
  departure_time: string;
  hos_state: HOSState;
}

export type RoutingSource = "osrm" | "haversine_fallback";

export interface TripPlanResponse {
  trip_id: string;
  total_distance_miles: number;
  total_driving_hours: number;
  total_trip_hours: number;
  routing_source: RoutingSource;
  route_geometry: [number, number][] | null;
  stops: StopMarker[];
  days: TripDay[];
  log_sheets: LogSheet[];
}

export interface TripPlanRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used: number;
}

// DRF's standard validation-error shape: { field_name: ["message", ...] }
export type ApiFieldErrors = Record<string, string[]>;
