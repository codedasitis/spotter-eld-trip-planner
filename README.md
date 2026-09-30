# Spotter AI: ELD Trip Planner

Takes a trip (current location, pickup, drop-off, current 70-hour/8-day
cycle used) and produces:

- An HOS-compliant route plan: driving segments, mandatory 10-hour resets,
  30-minute breaks, fuel stops every 1,000 miles, and 34-hour restarts
  when the cycle is exhausted mid-trip.
- A map of the route with typed stop markers and per-stop HOS state.
- One fully drawn, DOT-style daily log sheet (SVG, four duty-status rows)
  per calendar day the trip touches.

Built for the Spotter AI full-stack assessment: Django + DRF backend,
React + MUI frontend, Leaflet/OpenStreetMap map, OSRM routing with a
haversine fallback.

## Architecture, in one paragraph

All HOS business logic lives in one place: `backend/trips/hos_engine.py`,
a pure-Python class (`TripPlanner`) with zero Django/ORM dependency. The
Django view (`trips/views.py`) does exactly three things in order:
geocode the three locations (Nominatim), get route distances/durations
(OSRM, or a haversine estimate if OSRM is unavailable), and hand both to
`TripPlanner`. The React frontend never re-implements any of this; it
renders exactly what the API returns. The only math on the frontend is a
haversine distance helper (`src/utils/hosUtils.ts`) used purely to draw
the fallback straight-line route on the map.

## Quick start (local, one command)

```bash
cp .env.example .env   # optional, sane defaults work without this
docker-compose up --build
```

- Backend: http://localhost:8000/api/v1/trip/health/
- Frontend: http://localhost:5173

No Docker? Run each side directly:

```bash
# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# frontend, in a second terminal
cd frontend
npm install
npm run dev
```

## Running the tests

```bash
# backend: 14 tests (the 6 required behavioral tests, three covering
# the API contract, and five added after real-world testing surfaced
# location-labeling and rounding edge cases -- see the table below)
cd backend && source venv/bin/activate
python manage.py test trips -v 2

# frontend: 3 test files, 12 tests
cd frontend
npm test
```

Every backend test is a `django.test.TestCase`, fully isolated (no
class-level or module-level mutable state), and passes in randomized
order (`python manage.py test trips --shuffle`).

## What each test actually checks

| Test | What it would catch if the engine broke |
|---|---|
| `test_short_trip_no_rest_required` | A short trip growing a phantom rest stop, or a day's hours not summing to 24 |
| `test_cycle_exhaustion_raises` | The 70-hour check silently passing, or raising the wrong exception type |
| `test_cycle_exhaustion_detected_mid_trip_not_only_at_start` | Cycle exhaustion only being checked at t=0 instead of continuously |
| `test_fuel_stop_merged_into_rest` | A fuel stop and a mandatory rest colliding into a phantom zero-duration drive segment instead of one merged stop |
| `test_14_hour_window_closes_before_11_hour_drive` | The engine only checking the 11-hour driving cap and never the 14-hour wall-clock window |
| `test_multi_day_trip_log_sheets_total_24_each_day` | Any day's accounting (especially the first, which starts mid-morning) not summing to exactly 24.0 |
| `test_osrm_timeout_falls_back_to_haversine` | An OSRM outage crashing the request instead of gracefully falling back |
| `test_stop_forced_mid_leg_is_labeled_en_route_not_destination` | A mid-route stop (e.g. a 34-hour restart forced after one hour of driving) being mislabeled as though the driver had already arrived at the destination |
| `test_leading_padding_uses_start_location_not_upcoming_destination` | The off-duty gap before a trip starts being labeled with where the driver is headed instead of where they actually are |
| `test_daily_totals_sum_to_24_even_when_naive_per_bucket_rounding_would_not` | The four duty-status totals, rounded independently, displaying as 23.99 or 24.01 instead of exactly 24.0 |
| `DailyLogSheet.test.tsx` | The SVG renderer silently dropping a segment or mis-mapping a duty-status color |
| `TripForm.test.tsx` | Client-side validation calling the API with incomplete data |
| `hosUtils.test.ts` | The map's fallback-mode distance math being wrong |

## Bugs found and fixed via stress testing

Three real bugs were caught by testing edge cases past what the formal
suite originally covered, each with a regression test added afterward:

- **Mid-route stops mislabeled as the destination.** A cycle nearly
  exhausted at trip start (e.g. `current_cycle_used=69`) forces a
  34-hour restart after only an hour of driving, but the restart was
  being labeled with the leg's destination city rather than "en route"
  to it, as if the driver had already arrived hundreds of miles early.
  Fixed in `TripPlanner._drive_leg`; guarded by
  `test_stop_forced_mid_leg_is_labeled_en_route_not_destination`.
- **The gap before a trip even starts inherited the wrong location.**
  The off-duty padding before the first drive (e.g. 00:00-08:00) was
  labeled with wherever that first drive was headed, not with the
  driver's actual starting point. Fixed in `TripPlanner._pad_day_boundaries`;
  guarded by `test_leading_padding_uses_start_location_not_upcoming_destination`.
- **Independently-rounded duty totals not summing to 24.0.** Rounding
  each of the four duty-status totals to two decimals separately can
  make numbers that truly sum to 24.0 hours display as 23.99 or 24.01.
  Fixed with a largest-remainder rounding helper (`_round_preserving_sum`)
  so the displayed parts always sum to the displayed whole; guarded by
  `test_daily_totals_sum_to_24_even_when_naive_per_bucket_rounding_would_not`.

## Known simplifications (stated, not hidden)

- **Rolling 8-day window**: the assessment supplies a single scalar
  (`current_cycle_used`) rather than 7 days of prior duty history, so the
  engine tracks cycle usage as a running total that only *increases*
  until a 34-hour restart brings it back to zero. This never
  *under*-reports cycle usage, which is the safe direction to be wrong in for a
  compliance tool, but it isn't a byte-for-byte implementation of the
  true rolling window. Documented in `hos_engine.py`'s module docstring.
- **Sleeper berth vs. off-duty for rests**: the engine always logs a
  10-hour reset or 34-hour restart as `LINE_1_OFF_DUTY`, never
  `LINE_2_SLEEPER_BERTH` (both are legally valid ways to satisfy the
  reset). The renderer fully supports sleeper-berth rows, exercised by
  the `DailyLogSheet` test fixture; a future iteration could have the
  engine choose sleeper berth when a leg's equipment implies it.
- **Fuel stops merged with a 10-hour/34-hour reset are logged entirely as
  off-duty**, not split into a few minutes of on-duty-not-driving for the
  fueling itself. Stated in `hos_engine._insert_reset`.
- **Haversine fallback inflates straight-line distance by a fixed 1.25×**
  to approximate real road distance. It's a named heuristic, not routing
  data, and the UI always labels it as an estimate.

## Deployment

- **Backend → Render**: native Python runtime (no Dockerfile needed for
  Render itself; the repo's `Dockerfile` is for local `docker-compose`
  only). Build command: `pip install -r backend/requirements.txt`. Start
  command: `cd backend && gunicorn spotter.wsgi:application --bind
  0.0.0.0:$PORT`. Set environment variables `SECRET_KEY` (generate a real
  one), `DEBUG=False`, `ALLOWED_HOSTS=<your-render-domain>`,
  `CORS_ALLOWED_ORIGINS=<your-vercel-domain>`.
- **Frontend → Vercel**: root directory `frontend/`, framework preset
  Vite, build command `npm run build`, output directory `dist`. Set
  environment variable `VITE_API_BASE_URL=https://<your-render-domain>/api/v1`.

## Security checklist

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` all come
  from environment variables via `python-decouple`; the checked-in
  defaults are obviously-fake local-dev values.
- `DEBUG` defaults to `False`; local dev opts in via `.env`.
- No `CORS_ALLOW_ALL_ORIGINS` anywhere in the repo.
- Every Nominatim request sends the required `User-Agent` header and caps
  input length before it leaves the process.
- No location string is eval'd, shelled out, or used as a raw SQL
  fragment anywhere.
- `.env` is gitignored; only `.env.example` (placeholders + comments) is
  committed.
