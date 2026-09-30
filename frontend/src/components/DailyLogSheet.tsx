import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { DUTY_STATUS_COLORS } from "../theme";
import type { DailyTotals, DriverInfo, DutyStatus, Remark, Segment } from "../types";

// --- Coordinate system -------------------------------------------------
// Fixed contract: 1 hour = 60 SVG units, 1 duty-line row = 90 SVG units.
// 24 hours * 60 = 1440 wide. 4 rows * 90 = 360 tall. This mapping is
// exact and never scales with the fixture data -- that's what makes the
// renderer deterministic and testable.
export const VIEWBOX_WIDTH = 1440;
export const VIEWBOX_HEIGHT = 360;
const ROW_HEIGHT = 90;
const PX_PER_MINUTE = 60 / 60; // 60px per hour == 1px per minute

const ROW_ORDER: DutyStatus[] = [
  "LINE_1_OFF_DUTY",
  "LINE_2_SLEEPER_BERTH",
  "LINE_3_DRIVING",
  "LINE_4_ON_DUTY_NOT_DRIVING",
];

const ROW_LABELS: Record<DutyStatus, string> = {
  LINE_1_OFF_DUTY: "1. Off Duty",
  LINE_2_SLEEPER_BERTH: "2. Sleeper Berth",
  LINE_3_DRIVING: "3. Driving",
  LINE_4_ON_DUTY_NOT_DRIVING: "4. On Duty (Not Driving)",
};

const HOUR_LABELS = [
  "Mid", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
  "Noon", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23",
];

function rowIndex(status: DutyStatus): number {
  return ROW_ORDER.indexOf(status);
}

function rowCenterY(status: DutyStatus): number {
  return rowIndex(status) * ROW_HEIGHT + ROW_HEIGHT / 2;
}

function timeToX(time: string): number {
  if (time === "24:00") return VIEWBOX_WIDTH;
  const [hStr, mStr] = time.split(":");
  const minutes = parseInt(hStr, 10) * 60 + parseInt(mStr, 10);
  return minutes * PX_PER_MINUTE;
}

/**
 * A segment is a "real" event worth a remark line if its remark isn't the
 * generic day-boundary filler. The backend always writes exactly the
 * string "Off duty" for padding segments (see hos_engine._off_duty_filler)
 * -- everything else is a genuine status change with something to say.
 */
function isRemarkable(segment: Segment): boolean {
  return segment.remark !== "Off duty";
}

function deriveRemarks(daySegments: Segment[]): Remark[] {
  return daySegments
    .filter(isRemarkable)
    .map((s) => ({ time: s.start_time, location: s.location, activity: s.remark }));
}

function deriveDailyTotals(daySegments: Segment[]): DailyTotals {
  const totals = { line_1_hours: 0, line_2_hours: 0, line_3_hours: 0, line_4_hours: 0 };
  const key: Record<DutyStatus, keyof typeof totals> = {
    LINE_1_OFF_DUTY: "line_1_hours",
    LINE_2_SLEEPER_BERTH: "line_2_hours",
    LINE_3_DRIVING: "line_3_hours",
    LINE_4_ON_DUTY_NOT_DRIVING: "line_4_hours",
  };
  for (const s of daySegments) totals[key[s.duty_status]] += s.duration_hours;
  return {
    ...totals,
    total_on_duty_hours: round2(totals.line_3_hours + totals.line_4_hours),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export interface DailyLogSheetProps {
  /** The single required prop -- everything else has a sensible default
   * so the component renders deterministically from this alone. */
  daySegments: Segment[];
  date?: string;
  dayIndex?: number;
  driverInfo?: DriverInfo;
  /** When provided (normal app usage), these come straight from the
   * backend's log_sheets[] output and are rendered as-is. When omitted
   * (e.g. a standalone renderer test), they're derived from daySegments
   * by simple arithmetic -- summation, not a compliance decision -- so
   * the component still renders something correct on its own. */
  remarks?: Remark[];
  dailyTotals?: DailyTotals;
}

export default function DailyLogSheet({
  daySegments,
  date,
  dayIndex,
  driverInfo,
  remarks,
  dailyTotals,
}: DailyLogSheetProps) {
  const resolvedRemarks = remarks ?? deriveRemarks(daySegments);
  const resolvedTotals = dailyTotals ?? deriveDailyTotals(daySegments);

  return (
    <Box
      className="log-sheet-print-block"
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        p: { xs: 2, sm: 2.5 },
        bgcolor: "background.paper",
        boxShadow: "0 1px 2px rgba(28,26,22,0.04), 0 8px 24px rgba(28,26,22,0.03)",
      }}
    >
      <LogSheetHeader date={date} dayIndex={dayIndex} driverInfo={driverInfo} />

      <Box sx={{ display: "grid", gridTemplateColumns: "110px 1fr", mt: 2 }}>
        <Box />
        <Box sx={{ display: "flex" }}>
          {HOUR_LABELS.map((label, i) => (
            <Box key={i} sx={{ flex: 1, textAlign: "center" }}>
              <Typography variant="caption" sx={{ fontSize: "0.62rem", color: "text.secondary" }}>
                {label}
              </Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column" }}>
          {ROW_ORDER.map((status) => (
            <Box
              key={status}
              sx={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                pr: 1,
                borderRight: "2px solid",
                borderColor: DUTY_STATUS_COLORS[status],
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 600, fontSize: "0.68rem", lineHeight: 1.1 }}>
                {ROW_LABELS[status]}
              </Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ border: "1px solid #E3DCC9", bgcolor: "#FFFDF8" }}>
          <LogSheetGrid daySegments={daySegments} />
        </Box>
      </Box>

      <RemarksTable remarks={resolvedRemarks} />
      <TotalsRow totals={resolvedTotals} />
    </Box>
  );
}

function LogSheetHeader({
  date,
  dayIndex,
  driverInfo,
}: {
  date?: string;
  dayIndex?: number;
  driverInfo?: DriverInfo;
}) {
  const info = driverInfo ?? {
    tractor_number: "AUTO-001",
    trailer_number: "TRL-001",
    home_terminal: "-",
    shipper: "Assessment Trip",
    commodity: "General Freight",
    total_miles: 0,
  };
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 3, justifyContent: "space-between" }}>
      <Box>
        <Typography variant="subtitle1">
          {dayIndex !== undefined ? `Driver's Daily Log, Day ${dayIndex + 1}` : "Driver's Daily Log"}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {date ?? ""}
        </Typography>
      </Box>
      <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
        <Field label="Tractor #" value={info.tractor_number} />
        <Field label="Trailer #" value={info.trailer_number} />
        <Field label="Home Terminal" value={info.home_terminal} />
        <Field label="Shipper" value={info.shipper} />
        <Field label="Commodity" value={info.commodity} />
        <Field label="Miles Today" value={String(info.total_miles)} />
      </Box>
    </Box>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={600}>
        {value}
      </Typography>
    </Box>
  );
}

function LogSheetGrid({ daySegments }: { daySegments: Segment[] }) {
  return (
    <svg
      viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
      width="100%"
      height="auto"
      style={{ display: "block" }}
      role="img"
      aria-label="24-hour hours-of-service grid"
    >
      <GridBackground />
      {daySegments.map((segment, i) => (
        <SegmentMarks key={segment.id} segment={segment} previous={daySegments[i - 1]} />
      ))}
    </svg>
  );
}

function GridBackground() {
  const hourLines = [];
  for (let h = 0; h <= 24; h++) {
    const x = h * 60;
    hourLines.push(
      <line
        key={`hour-${h}`}
        x1={x}
        y1={0}
        x2={x}
        y2={VIEWBOX_HEIGHT}
        stroke="#E3DCC9"
        strokeWidth={h % 6 === 0 ? 1.2 : 0.8}
      />
    );
    if (h < 24) {
      for (const q of [15, 30, 45]) {
        const qx = x + q;
        for (let row = 0; row < 4; row++) {
          const rowTop = row * ROW_HEIGHT;
          hourLines.push(
            <line
              key={`tick-${h}-${q}-${row}`}
              x1={qx}
              y1={rowTop}
              x2={qx}
              y2={rowTop + 8}
              stroke="#E3DCC9"
              strokeWidth={0.6}
            />
          );
        }
      }
    }
  }
  const rowLines = [1, 2, 3].map((r) => (
    <line
      key={`row-${r}`}
      x1={0}
      y1={r * ROW_HEIGHT}
      x2={VIEWBOX_WIDTH}
      y2={r * ROW_HEIGHT}
      stroke="#B7AE96"
      strokeWidth={1}
    />
  ));
  return (
    <g data-testid="grid-background">
      {hourLines}
      {rowLines}
    </g>
  );
}

function SegmentMarks({ segment, previous }: { segment: Segment; previous?: Segment }) {
  const x1 = timeToX(segment.start_time);
  const x2 = timeToX(segment.end_time);
  const y = rowCenterY(segment.duty_status);
  const color = DUTY_STATUS_COLORS[segment.duty_status];

  const showConnector = previous && previous.duty_status !== segment.duty_status;
  const showBracket = segment.is_stationary && x2 > x1;
  const showFlag = previous && isRemarkable(segment);

  return (
    <g>
      {/* The horizontal duty-status line -- this is the one element per
          segment that data-segment-id refers to. Connectors, brackets,
          and flags below are drawn *for* this segment but intentionally
          do not carry data-segment-id themselves, so a test counting
          `line[data-segment-id]` gets exactly one hit per real segment. */}
      <line
        data-segment-id={segment.id}
        data-duty-status={segment.duty_status}
        x1={x1}
        y1={y}
        x2={x2}
        y2={y}
        stroke={color}
        strokeWidth={3}
        strokeLinecap="square"
      />

      {showConnector && (
        <line
          data-connector-for={segment.id}
          x1={x1}
          y1={rowCenterY(previous!.duty_status)}
          x2={x1}
          y2={y}
          stroke="#2B2822"
          strokeWidth={1.5}
        />
      )}

      {showBracket && (
        <path
          data-bracket-for={segment.id}
          d={`M ${x1} ${y} L ${x1} ${y + 16} L ${x2} ${y + 16} L ${x2} ${y}`}
          fill="none"
          stroke={color}
          strokeWidth={1}
          strokeDasharray="2 2"
        />
      )}

      {showFlag && (
        <polygon
          data-flag-for={segment.id}
          points={`${x1 - 5},${VIEWBOX_HEIGHT} ${x1 + 5},${VIEWBOX_HEIGHT} ${x1},${VIEWBOX_HEIGHT + 10}`}
          fill="#2B2822"
        />
      )}
    </g>
  );
}

function RemarksTable({ remarks }: { remarks: Remark[] }) {
  return (
    <Box sx={{ mt: 3 }}>
      <Typography
        variant="caption"
        fontWeight={700}
        color="text.secondary"
        sx={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.66rem" }}
      >
        Remarks
      </Typography>
      <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", mt: 0.5 }}>
        <Box component="thead">
          <Box component="tr">
            {["Time", "Location", "Activity"].map((h) => (
              <Box
                component="th"
                key={h}
                sx={{ textAlign: "left", fontSize: "0.72rem", color: "text.secondary", pb: 0.5, borderBottom: "1px solid #E3DCC9" }}
              >
                {h}
              </Box>
            ))}
          </Box>
        </Box>
        <Box component="tbody">
          {remarks.map((r, i) => (
            <Box component="tr" key={i}>
              <Box component="td" sx={{ fontSize: "0.8rem", py: 0.4, width: 60 }}>
                {r.time}
              </Box>
              <Box component="td" sx={{ fontSize: "0.8rem", py: 0.4, width: 180 }}>
                {r.location}
              </Box>
              <Box component="td" sx={{ fontSize: "0.8rem", py: 0.4 }}>
                {r.activity}
              </Box>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  );
}

function TotalsRow({ totals }: { totals: DailyTotals }) {
  const items: [string, DutyStatus | null, number][] = [
    ["Off Duty", "LINE_1_OFF_DUTY", totals.line_1_hours],
    ["Sleeper Berth", "LINE_2_SLEEPER_BERTH", totals.line_2_hours],
    ["Driving", "LINE_3_DRIVING", totals.line_3_hours],
    ["On Duty (Not Driving)", "LINE_4_ON_DUTY_NOT_DRIVING", totals.line_4_hours],
  ];
  return (
    <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 3, borderTop: "1px solid #E3DCC9", pt: 1.5 }}>
      {items.map(([label, status, value]) => (
        <Box key={label} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: status ? DUTY_STATUS_COLORS[status] : "grey.400" }} />
          <Typography variant="caption" color="text.secondary">
            {label}:
          </Typography>
          <Typography variant="body2" fontWeight={700}>
            {value.toFixed(2)}h
          </Typography>
        </Box>
      ))}
      <Box sx={{ ml: "auto" }}>
        <Typography variant="body2" fontWeight={700}>
          Total on-duty: {totals.total_on_duty_hours.toFixed(2)}h
        </Typography>
      </Box>
    </Box>
  );
}
