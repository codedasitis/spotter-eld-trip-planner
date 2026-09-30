import Alert from "@mui/material/Alert";
import Collapse from "@mui/material/Collapse";

export interface StatusBarProps {
  backendHealthy: boolean | null;
}

/**
 * Only renders anything once we know the backend is unreachable -- a
 * "checking..." or "online" state doesn't need to occupy permanent space
 * at the top of the page, but an outage should be impossible to miss.
 */
export default function StatusBar({ backendHealthy }: StatusBarProps) {
  return (
    <Collapse in={backendHealthy === false}>
      <Alert severity="error" square sx={{ borderRadius: 0 }}>
        Backend unreachable. Trip planning is unavailable until the API comes back online.
      </Alert>
    </Collapse>
  );
}
