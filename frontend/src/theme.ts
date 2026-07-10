import { createTheme } from "@mui/material/styles";
import type { PaletteMode } from "@mui/material";

export function buildTheme(mode: PaletteMode) {
  const isDark = mode === "dark";
  return createTheme({
    cssVariables: true,
    palette: {
      mode,
      primary: { main: "#1565c0" },
      secondary: { main: "#00897b" },
      background: {
        default: isDark ? "#0f1417" : "#f4f6f8",
        paper: isDark ? "#1a2027" : "#ffffff",
      },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      h6: { fontWeight: 600 },
      subtitle2: { fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5 },
    },
    components: {
      MuiAppBar: {
        defaultProps: { elevation: 0 },
      },
      MuiButton: {
        styleOverrides: {
          root: { textTransform: "none", fontWeight: 600 },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { border: "1px solid", borderColor: isDark ? "#2a323a" : "#e0e4e8" },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: "none" },
        },
      },
    },
  });
}
