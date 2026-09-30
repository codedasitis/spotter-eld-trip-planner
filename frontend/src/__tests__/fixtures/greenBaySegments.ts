import type { HOSState, Segment } from "../../types";

// Verbatim from the Schneider "how to fill out a log book" training video:
// a driver's day from Green Bay, WI through Fond du Lac, Paw Paw, and
// Edwardsville. This is authored by hand from the video's own state
// machine table -- it is not engine output -- specifically so the
// DailyLogSheet renderer can be tested against all four duty-status rows
// (including sleeper berth, which this assessment's simplified engine
// never emits) with numbers whose correctness is independently checkable
// against the source video.

const zeroState: HOSState = {
  cycle_hours_used: 0,
  driving_hours_today: 0,
  on_duty_hours_today: 0,
  hours_since_last_break: 0,
  window_opened_at: null,
};

function seg(partial: Omit<Segment, "hos_state" | "day_index">): Segment {
  return { ...partial, day_index: 0, hos_state: zeroState };
}

export const greenBaySegments: Segment[] = [
  seg({
    id: "gb-1",
    type: "OFF_DUTY",
    duty_status: "LINE_1_OFF_DUTY",
    start_time: "00:00",
    end_time: "06:30",
    duration_hours: 6.5,
    location: "Green Bay, WI",
    remark: "Off duty",
    is_stationary: true,
    miles_this_segment: 0,
  }),
  seg({
    id: "gb-2",
    type: "ON_DUTY",
    duty_status: "LINE_4_ON_DUTY_NOT_DRIVING",
    start_time: "06:30",
    end_time: "07:00",
    duration_hours: 0.5,
    location: "Green Bay, WI",
    remark: "Pre-trip inspection + trailer integrity verification",
    is_stationary: true,
    miles_this_segment: 0,
  }),
  seg({
    id: "gb-3",
    type: "DRIVE",
    duty_status: "LINE_3_DRIVING",
    start_time: "07:00",
    end_time: "09:30",
    duration_hours: 2.5,
    location: "En route to Fond du Lac, WI",
    remark: "Driving",
    is_stationary: false,
    miles_this_segment: 130,
  }),
  seg({
    id: "gb-4",
    type: "ON_DUTY",
    duty_status: "LINE_4_ON_DUTY_NOT_DRIVING",
    start_time: "09:30",
    end_time: "10:00",
    duration_hours: 0.5,
    location: "Fond du Lac, WI",
    remark: "Cat scale + fuel",
    is_stationary: true,
    miles_this_segment: 0,
  }),
  seg({
    id: "gb-5",
    type: "DRIVE",
    duty_status: "LINE_3_DRIVING",
    start_time: "10:00",
    end_time: "13:00",
    duration_hours: 3.0,
    location: "En route to Paw Paw, IL",
    remark: "Driving",
    is_stationary: false,
    miles_this_segment: 160,
  }),
  seg({
    id: "gb-6",
    type: "BREAK",
    duty_status: "LINE_1_OFF_DUTY",
    start_time: "13:00",
    end_time: "13:30",
    duration_hours: 0.5,
    location: "Paw Paw, IL",
    remark: "Mandatory 30-minute break",
    is_stationary: true,
    miles_this_segment: 0,
  }),
  seg({
    id: "gb-7",
    type: "DRIVE",
    duty_status: "LINE_3_DRIVING",
    start_time: "13:30",
    end_time: "17:30",
    duration_hours: 4.0,
    location: "En route to Edwardsville, IL",
    remark: "Driving",
    is_stationary: false,
    miles_this_segment: 210,
  }),
  seg({
    id: "gb-8",
    type: "OFF_DUTY",
    duty_status: "LINE_1_OFF_DUTY",
    start_time: "17:30",
    end_time: "19:00",
    duration_hours: 1.5,
    location: "Edwardsville, IL",
    remark: "Post-trip inspection",
    is_stationary: true,
    miles_this_segment: 0,
  }),
  seg({
    id: "gb-9",
    type: "SLEEPER",
    duty_status: "LINE_2_SLEEPER_BERTH",
    start_time: "19:00",
    end_time: "24:00",
    duration_hours: 5.0,
    location: "Edwardsville, IL",
    remark: "Sleeper berth (overnight)",
    is_stationary: true,
    miles_this_segment: 0,
  }),
];
