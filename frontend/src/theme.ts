import { createTheme } from "@mui/material/styles";

// A working-log aesthetic rather than a generic SaaS dashboard: warm
// paper background (this product's whole output is a paper log sheet,
// so the chrome around it should feel like the same material), a near
// ink primary instead of stock MUI blue, and a single restrained amber
// accent used sparingly rather than color everywhere.
const INK = "#1C1A16";
const PAPER = "#F6F2E9";
const PAPER_CARD = "#FFFDF8";
const HAIRLINE = "#E3DCC9";
const ACCENT = "#9A5B23";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: INK, light: "#3A362F", dark: "#0E0D0B", contrastText: PAPER_CARD },
    secondary: { main: ACCENT },
    background: { default: PAPER, paper: PAPER_CARD },
    success: { main: "#3F7A4E" },
    warning: { main: ACCENT },
    error: { main: "#A23B2E" },
    divider: HAIRLINE,
    text: { primary: INK, secondary: "#6B6455" },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: '"Inter", "Segoe UI", Roboto, system-ui, sans-serif',
    h6: {
      fontFamily: '"Source Serif 4", Georgia, serif',
      fontWeight: 600,
      letterSpacing: "-0.01em",
    },
    subtitle1: {
      fontFamily: '"Source Serif 4", Georgia, serif',
      fontWeight: 600,
    },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: "0.01em" },
    caption: { letterSpacing: "0.01em" },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: INK,
          backgroundImage: "none",
          borderBottom: `2px solid ${ACCENT}`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: `1px solid ${HAIRLINE}`,
          boxShadow: "0 1px 2px rgba(28,26,22,0.04), 0 8px 24px rgba(28,26,22,0.03)",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 6, paddingInline: "18px" },
        containedPrimary: {
          backgroundColor: INK,
          "&:hover": { backgroundColor: "#0E0D0B" },
        },
        outlined: { borderColor: HAIRLINE, color: INK },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: "#FBF8F1",
          "& fieldset": { borderColor: HAIRLINE },
          "&:hover fieldset": { borderColor: "#C9BE9E" },
          "&.Mui-focused fieldset": { borderColor: ACCENT, borderWidth: 1 },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: { "&.Mui-focused": { color: ACCENT } },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 8 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
  },
});

// Duty-status colors: load-bearing constants, not style choices. They
// are referenced by both DailyLogSheet (the SVG grid, and asserted
// exactly in its test) and TripMap's legend, and they are exactly what
// the assessment brief specifies. They do not move for a visual refresh.
export const DUTY_STATUS_COLORS: Record<string, string> = {
  LINE_1_OFF_DUTY: "#4B5563",
  LINE_2_SLEEPER_BERTH: "#6366F1",
  LINE_3_DRIVING: "#10B981",
  LINE_4_ON_DUTY_NOT_DRIVING: "#F59E0B",
};

export const STOP_TYPE_COLORS: Record<string, string> = {
  PICKUP: "#059669",
  DROPOFF: "#A23B2E",
  REST: "#2563EB",
  REST_AND_FUEL: "#2563EB",
  RESTART_34: "#2563EB",
  FUEL: "#9A5B23",
  BREAK: "#6B6455",
};

export const THEME_TOKENS = { INK, PAPER, PAPER_CARD, HAIRLINE, ACCENT };
