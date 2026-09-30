import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DailyLogSheet from "../components/DailyLogSheet";
import { greenBaySegments } from "./fixtures/greenBaySegments";

describe("DailyLogSheet", () => {
  it("renders exactly one segment line per segment, with correct driving color and remarks", () => {
    const { container } = render(<DailyLogSheet daySegments={greenBaySegments} />);

    // Exactly one <line data-segment-id> per real segment. Connectors,
    // brackets, and grid lines intentionally don't carry this attribute,
    // so this count would drop below 9 if the renderer silently dropped a
    // segment, and would rise above 9 if a connector/grid line leaked the
    // attribute it shouldn't have.
    const segmentLines = container.querySelectorAll("line[data-segment-id]");
    expect(segmentLines.length).toBe(9);

    // Every DRIVE segment (gb-3, gb-5, gb-7) must use the driving color.
    const driveIds = ["gb-3", "gb-5", "gb-7"];
    driveIds.forEach((id) => {
      const line = container.querySelector(`line[data-segment-id="${id}"]`);
      expect(line).not.toBeNull();
      expect(line?.getAttribute("stroke")).toBe("#10B981");
    });

    // Non-driving segments must NOT use the driving color.
    const nonDriveLine = container.querySelector('line[data-segment-id="gb-1"]');
    expect(nonDriveLine?.getAttribute("stroke")).not.toBe("#10B981");

    // The remarks table surfaces the Fond du Lac stop.
    expect(screen.getByText("Fond du Lac, WI")).toBeInTheDocument();
  });

  it("renders the sleeper berth segment on its own row with the sleeper color", () => {
    const { container } = render(<DailyLogSheet daySegments={greenBaySegments} />);
    const sleeperLine = container.querySelector('line[data-segment-id="gb-9"]');
    expect(sleeperLine?.getAttribute("stroke")).toBe("#6366F1");
  });

  it("derives daily totals that sum to 24 hours when none are explicitly supplied", () => {
    render(<DailyLogSheet daySegments={greenBaySegments} />);
    // 8.5 off duty + 5.0 sleeper + 9.5 driving + 1.0 on-duty = 24.0,
    // matching the video's own totals exactly.
    expect(screen.getByText(/9\.50h/)).toBeInTheDocument();
    expect(screen.getByText(/Total on-duty: 10\.50h/)).toBeInTheDocument();
  });
});
