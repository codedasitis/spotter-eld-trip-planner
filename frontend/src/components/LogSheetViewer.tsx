import PrintIcon from "@mui/icons-material/Print";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import DailyLogSheet from "./DailyLogSheet";
import type { LogSheet } from "../types";

export interface LogSheetViewerProps {
  logSheets: LogSheet[];
}

export default function LogSheetViewer({ logSheets }: LogSheetViewerProps) {
  if (logSheets.length === 0) return null;

  return (
    <Box>
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{ mb: 2.5, pb: 1.5, borderBottom: "1px solid", borderColor: "divider" }}
      >
        <Typography variant="h6">Daily log sheets ({logSheets.length})</Typography>
        <Button
          size="small"
          variant="outlined"
          startIcon={<PrintIcon fontSize="small" />}
          onClick={() => window.print()}
          className="no-print"
        >
          Print / Export PDF
        </Button>
      </Stack>

      <Stack spacing={3}>
        {logSheets.map((sheet) => (
          <DailyLogSheet
            key={sheet.day_index}
            daySegments={sheet.grid_segments}
            date={sheet.date}
            dayIndex={sheet.day_index}
            driverInfo={sheet.driver_info}
            remarks={sheet.remarks}
            dailyTotals={sheet.daily_totals}
          />
        ))}
      </Stack>
    </Box>
  );
}
