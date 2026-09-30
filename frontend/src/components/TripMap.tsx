import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import { STOP_TYPE_COLORS } from "../theme";
import type { RoutingSource, StopMarker } from "../types";

function coloredPinIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<svg width="26" height="34" viewBox="0 0 26 34" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 0C5.8 0 0 5.8 0 13c0 9.7 13 21 13 21s13-11.3 13-21c0-7.2-5.8-13-13-13z" fill="${color}" stroke="#ffffff" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="5" fill="#ffffff"/>
    </svg>`,
    iconSize: [26, 34],
    iconAnchor: [13, 34],
    popupAnchor: [0, -30],
  });
}

const ICONS: Record<string, L.DivIcon> = Object.fromEntries(
  Object.entries(STOP_TYPE_COLORS).map(([type, color]) => [type, coloredPinIcon(color)])
);

function iconFor(type: string): L.DivIcon {
  return ICONS[type] ?? coloredPinIcon("#334155");
}

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useMemo(() => {
    if (points.length > 0) {
      map.fitBounds(points, { padding: [40, 40] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points.map((p) => p.join(",")).join("|")]);
  return null;
}

/**
 * Leaflet measures its container's width the instant it mounts. Inside a
 * flex/grid layout (this map sits in an MUI Grid column) that width is
 * not always final yet, so the map can initialize a size or two narrow
 * and leave a blank strip on one side until something forces a
 * recalculation. A ResizeObserver on the map's own container, plus one
 * immediate invalidateSize call, fixes this at the source rather than
 * papering over it with a fixed pixel width.
 */
function MapResizeHandler() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container);
    const raf = requestAnimationFrame(() => map.invalidateSize());
    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [map]);
  return null;
}

export interface TripMapProps {
  stops: StopMarker[];
  routeGeometry: [number, number][] | null;
  routingSource: RoutingSource;
}

export default function TripMap({ stops, routeGeometry, routingSource }: TripMapProps) {
  const fallbackLine: [number, number][] = useMemo(
    () => stops.map((s) => [s.latitude, s.longitude]),
    [stops]
  );
  const polylinePoints = routeGeometry && routeGeometry.length > 0 ? routeGeometry : fallbackLine;
  const boundsPoints = polylinePoints.length > 0 ? polylinePoints : fallbackLine;

  return (
    <Paper
      elevation={0}
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        overflow: "hidden",
        boxShadow: "0 1px 2px rgba(28,26,22,0.04), 0 8px 24px rgba(28,26,22,0.03)",
      }}
    >
      {routingSource === "haversine_fallback" && (
        <Alert severity="warning" sx={{ borderRadius: 0 }}>
          Route data estimated: live routing unavailable
        </Alert>
      )}

      <Box sx={{ height: { xs: 320, sm: 420 }, width: "100%" }}>
        {stops.length === 0 ? (
          <Stack alignItems="center" justifyContent="center" sx={{ height: "100%", bgcolor: "#FBF8F1" }}>
            <Typography variant="body2" color="text.secondary">
              Plan a trip to see the route.
            </Typography>
          </Stack>
        ) : (
          <MapContainer
            center={boundsPoints[0]}
            zoom={6}
            style={{ height: "100%", width: "100%" }}
            scrollWheelZoom={false}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitBounds points={boundsPoints} />
            <MapResizeHandler />
            <Polyline
              positions={polylinePoints}
              pathOptions={{
                color: routingSource === "haversine_fallback" ? "#9A5B23" : "#2563EB",
                weight: 4,
                dashArray: routingSource === "haversine_fallback" ? "8 8" : undefined,
              }}
            />
            {stops.map((stop, i) => (
              <Marker key={i} position={[stop.latitude, stop.longitude]} icon={iconFor(stop.type)}>
                <Popup>
                  <Stack spacing={0.5} sx={{ minWidth: 190 }}>
                    <Typography variant="subtitle2">{stop.type.replace(/_/g, " ")}</Typography>
                    <Typography variant="body2">{stop.location}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Arrive {stop.arrival_time} / Depart {stop.departure_time}
                    </Typography>
                    <Box sx={{ borderTop: "1px solid #E3DCC9", mt: 0.5, pt: 0.5 }}>
                      <Typography variant="caption" display="block">
                        Cycle used: {stop.hos_state.cycle_hours_used.toFixed(1)}h / 70h
                      </Typography>
                      <Typography variant="caption" display="block">
                        Driving today: {stop.hos_state.driving_hours_today.toFixed(1)}h
                      </Typography>
                      <Typography variant="caption" display="block">
                        Since last break: {stop.hos_state.hours_since_last_break.toFixed(1)}h
                      </Typography>
                    </Box>
                  </Stack>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        )}
      </Box>

      <StopList stops={stops} />
    </Paper>
  );
}

function StopList({ stops }: { stops: StopMarker[] }) {
  if (stops.length === 0) return null;
  return (
    <Box sx={{ p: 2, maxHeight: 220, overflowY: "auto" }}>
      <Typography
        variant="caption"
        fontWeight={700}
        color="text.secondary"
        sx={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.66rem" }}
      >
        Stops
      </Typography>
      <Stack spacing={1} sx={{ mt: 1 }}>
        {stops.map((stop, i) => (
          <Stack key={i} direction="row" justifyContent="space-between" alignItems="center">
            <Box>
              <Typography variant="body2" fontWeight={600}>
                {stop.type.replace(/_/g, " ")} at {stop.location}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {stop.arrival_time} to {stop.departure_time} / cycle {stop.hos_state.cycle_hours_used.toFixed(1)}h used
              </Typography>
            </Box>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}
