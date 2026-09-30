import { describe, expect, it } from "vitest";
import { haversineDistanceMiles } from "../utils/hosUtils";

describe("haversineDistanceMiles", () => {
  it("returns the great-circle distance between Chicago and St. Louis in miles", () => {
    const distance = haversineDistanceMiles(
      "Chicago, IL",
      [41.8781, -87.6298],
      [38.627, -90.1994]
    );
    // Actual road distance is ~300mi; straight-line great-circle distance
    // is a bit shorter than that, in the ~260-300 range.
    expect(distance).toBeGreaterThan(260);
    expect(distance).toBeLessThan(300);
  });

  it("returns 0 for identical coordinates", () => {
    const distance = haversineDistanceMiles("same point", [40.0, -90.0], [40.0, -90.0]);
    expect(distance).toBeCloseTo(0, 5);
  });

  it("throws on non-finite coordinates instead of silently returning NaN", () => {
    expect(() => haversineDistanceMiles("bad input", [NaN, 0], [0, 0])).toThrow();
  });
});
