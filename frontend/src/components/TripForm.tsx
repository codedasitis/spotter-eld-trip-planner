import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import type { ApiFieldErrors, TripPlanRequest } from "../types";

export interface TripFormProps {
  onSubmit: (request: TripPlanRequest) => void;
  loading: boolean;
  backendHealthy: boolean | null;
  fieldErrors?: ApiFieldErrors | null;
  networkError?: string | null;
}

interface FormState {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used: string;
}

const EMPTY_FORM: FormState = {
  current_location: "",
  pickup_location: "",
  dropoff_location: "",
  current_cycle_used: "",
};

export default function TripForm({ onSubmit, loading, backendHealthy, fieldErrors, networkError }: TripFormProps) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({});

  const cycleValue = parseFloat(form.current_cycle_used);
  const cycleOutOfRange =
    form.current_cycle_used !== "" && (Number.isNaN(cycleValue) || cycleValue < 0 || cycleValue > 70);

  function handleChange(field: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setLocalErrors((prev) => ({ ...prev, [field]: "" }));
    };
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!form.current_location.trim()) errors.current_location = "Current location is required.";
    if (!form.pickup_location.trim()) errors.pickup_location = "Pickup location is required.";
    if (!form.dropoff_location.trim()) errors.dropoff_location = "Drop-off location is required.";
    if (form.current_cycle_used === "") {
      errors.current_cycle_used = "Current cycle hours used is required.";
    } else if (cycleOutOfRange) {
      errors.current_cycle_used = "Enter a value between 0 and 70.";
    }
    setLocalErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({
      current_location: form.current_location.trim(),
      pickup_location: form.pickup_location.trim(),
      dropoff_location: form.dropoff_location.trim(),
      current_cycle_used: cycleValue,
    });
  }

  const errorFor = (field: string): string | undefined => localErrors[field] || fieldErrors?.[field]?.[0];

  const submitDisabled = loading || cycleOutOfRange;

  return (
    <Paper
      component="form"
      onSubmit={handleSubmit}
      // `step={0.5}` below governs the number input's spinner arrows, but
      // the browser also uses it for native constraint validation, which
      // silently blocks the whole submit event (before this component's
      // own onSubmit ever runs) for a value like 69.9 that isn't a
      // multiple of 0.5 from 0, even though 0-70 as a plain range is all
      // that this form's own validate() and the backend actually
      // enforce. `noValidate` hands that back to this component instead
      // of the browser's stricter, silent rejection.
      noValidate
      elevation={0}
      sx={{
        p: { xs: 2.5, sm: 3.5 },
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        boxShadow: "0 1px 2px rgba(28,26,22,0.04), 0 8px 24px rgba(28,26,22,0.03)",
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{ mb: 2.5, pb: 1.5, borderBottom: "1px solid", borderColor: "divider" }}
      >
        <Typography variant="h6">Plan a trip</Typography>
        <BackendStatus backendHealthy={backendHealthy} />
      </Stack>

      {networkError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {networkError}
        </Alert>
      )}

      <Stack spacing={2.25}>
        <TextField
          label="Current location"
          placeholder="e.g. Chicago, IL"
          value={form.current_location}
          onChange={handleChange("current_location")}
          error={Boolean(errorFor("current_location"))}
          helperText={errorFor("current_location")}
          fullWidth
        />
        <TextField
          label="Pickup location"
          placeholder="e.g. St. Louis, MO"
          value={form.pickup_location}
          onChange={handleChange("pickup_location")}
          error={Boolean(errorFor("pickup_location"))}
          helperText={errorFor("pickup_location")}
          fullWidth
        />
        <TextField
          label="Drop-off location"
          placeholder="e.g. Nashville, TN"
          value={form.dropoff_location}
          onChange={handleChange("dropoff_location")}
          error={Boolean(errorFor("dropoff_location"))}
          helperText={errorFor("dropoff_location")}
          fullWidth
        />
        <TextField
          label="Current cycle used (hrs)"
          type="number"
          inputProps={{ min: 0, max: 70, step: 0.5 }}
          value={form.current_cycle_used}
          onChange={handleChange("current_cycle_used")}
          error={Boolean(errorFor("current_cycle_used"))}
          helperText={errorFor("current_cycle_used") || "70/8-day cycle, property-carrying driver"}
          fullWidth
        />

        <Box sx={{ pt: 0.5 }}>
          <Button
            type="submit"
            variant="contained"
            disabled={submitDisabled}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {loading ? "Planning trip..." : "Plan trip"}
          </Button>
        </Box>
      </Stack>
    </Paper>
  );
}

function BackendStatus({ backendHealthy }: { backendHealthy: boolean | null }) {
  const state =
    backendHealthy === null
      ? { color: "#B7AE96", label: "Checking backend..." }
      : backendHealthy
        ? { color: "#3F7A4E", label: "Backend online" }
        : { color: "#A23B2E", label: "Backend unreachable" };

  return (
    <Stack direction="row" alignItems="center" spacing={0.9}>
      <Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: state.color, flexShrink: 0 }} />
      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
        {state.label}
      </Typography>
    </Stack>
  );
}
