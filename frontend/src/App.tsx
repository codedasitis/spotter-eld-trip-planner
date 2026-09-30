import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { ApiValidationError, checkHealth, NetworkError, planTrip } from "./api/tripApi";
import LogSheetViewer from "./components/LogSheetViewer";
import StatusBar from "./components/StatusBar";
import TripForm from "./components/TripForm";
import TripMap from "./components/TripMap";
import { THEME_TOKENS } from "./theme";
import type { ApiFieldErrors, TripPlanRequest, TripPlanResponse } from "./types";

export default function App() {
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [tripResult, setTripResult] = useState<TripPlanResponse | null>(null);
  const [fieldErrors, setFieldErrors] = useState<ApiFieldErrors | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);

  useEffect(() => {
    // Polled once on mount, deliberately not on an interval: this is a
    // load-time availability check, not a live heartbeat.
    checkHealth().then(setBackendHealthy);
  }, []);

  async function handleSubmit(request: TripPlanRequest) {
    setLoading(true);
    setFieldErrors(null);
    setNetworkError(null);
    try {
      const result = await planTrip(request);
      setTripResult(result);
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setFieldErrors(err.fieldErrors);
      } else if (err instanceof NetworkError) {
        setNetworkError(err.message);
      } else {
        setNetworkError("Something went wrong planning this trip. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <AppBar position="static" elevation={0} className="no-print">
        <Toolbar sx={{ minHeight: 60, px: { xs: 2, sm: 3 } }}>
          <Stack direction="row" alignItems="baseline" spacing={1.25} sx={{ flexGrow: 1 }}>
            <Typography variant="h6" sx={{ color: THEME_TOKENS.PAPER_CARD, fontSize: "1.15rem" }}>
              Spotter
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "rgba(246,242,233,0.55)",
                textTransform: "uppercase",
                letterSpacing: "0.14em",
                fontSize: "0.68rem",
              }}
            >
              ELD Trip Planner
            </Typography>
          </Stack>
        </Toolbar>
      </AppBar>
      <Box className="no-print">
        <StatusBar backendHealthy={backendHealthy} />
      </Box>

      <Container maxWidth="lg" sx={{ py: { xs: 3, sm: 5 } }}>
        <Stack spacing={5}>
          <Grid container spacing={3} className="no-print">
            <Grid item xs={12} md={5}>
              <TripForm
                onSubmit={handleSubmit}
                loading={loading}
                backendHealthy={backendHealthy}
                fieldErrors={fieldErrors}
                networkError={networkError}
              />
            </Grid>
            <Grid item xs={12} md={7}>
              {tripResult ? (
                <TripMap
                  stops={tripResult.stops}
                  routeGeometry={tripResult.route_geometry}
                  routingSource={tripResult.routing_source}
                />
              ) : (
                <TripMap stops={[]} routeGeometry={null} routingSource="osrm" />
              )}
            </Grid>
          </Grid>

          {tripResult && (
            <>
              <Box className="no-print">
                <TripSummary result={tripResult} />
              </Box>
              <LogSheetViewer logSheets={tripResult.log_sheets} />
            </>
          )}
        </Stack>
      </Container>
    </Box>
  );
}

function TripSummary({ result }: { result: TripPlanResponse }) {
  const items = [
    { label: "Total distance", value: `${result.total_distance_miles.toFixed(1)} mi` },
    { label: "Total driving time", value: `${result.total_driving_hours.toFixed(1)} h` },
    { label: "Total trip duration", value: `${result.total_trip_hours.toFixed(1)} h` },
    { label: "Log sheets generated", value: String(result.log_sheets.length) },
    {
      label: "Routing source",
      value: result.routing_source === "osrm" ? "Live (OSRM)" : "Estimated (haversine)",
    },
  ];
  return (
    <Paper
      variant="outlined"
      sx={{
        borderColor: "divider",
        borderRadius: 2,
        overflow: "hidden",
      }}
    >
      <Stack direction={{ xs: "column", sm: "row" }} divider={<Box sx={{ width: "1px", bgcolor: "divider" }} />}>
        {items.map((item) => (
          <Box key={item.label} sx={{ flex: 1, px: 2.5, py: 1.75 }}>
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              sx={{ textTransform: "uppercase", fontSize: "0.66rem", letterSpacing: "0.08em" }}
            >
              {item.label}
            </Typography>
            <Typography variant="subtitle2" sx={{ mt: 0.25 }}>
              {item.value}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}
