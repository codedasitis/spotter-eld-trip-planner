// This file intentionally contains ONLY geographic math (a straight-line
// distance calculation), never HOS rules. All duty-status, rest, and
// cycle logic lives exclusively in the Django backend
// (trips/hos_engine.py) -- duplicating any of it here would be a bug per
// the project's own architecture rule. This utility exists purely to
// draw the "estimated" straight-line route on the map when the backend
// reports routing_source === "haversine_fallback" and no real geometry
// is available.

const EARTH_RADIUS_MILES = 3958.8;

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

/**
 * Great-circle distance between two (lat, lon) points, in miles.
 *
 * `label` identifies what's being measured (e.g. "Chicago, IL") purely
 * for developer-facing error context if the coordinates turn out to be
 * invalid -- it never affects the computed distance.
 */
export function haversineDistanceMiles(
  label: string,
  from: [number, number],
  to: [number, number]
): number {
  const [lat1, lon1] = from;
  const [lat2, lon2] = to;

  for (const value of [lat1, lon1, lat2, lon2]) {
    if (Number.isNaN(value) || !Number.isFinite(value)) {
      throw new Error(`haversineDistanceMiles: invalid coordinate for "${label}"`);
    }
  }

  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.asin(Math.sqrt(a));

  return EARTH_RADIUS_MILES * c;
}
