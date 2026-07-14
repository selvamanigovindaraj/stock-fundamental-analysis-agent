import { useMemo, useState } from "react";
import type { JSX } from "react";
import {
  AppBar,
  Box,
  Container,
  CssBaseline,
  IconButton,
  Paper,
  Stack,
  ThemeProvider,
  Toolbar,
  Typography,
} from "@mui/material";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import InsightsIcon from "@mui/icons-material/Insights";
import { TickerForm } from "./components/TickerForm";
import { StatusBanner } from "./components/StatusBanner";
import { RatiosCard } from "./components/RatiosCard";
import { ReportCard } from "./components/ReportCard";
import { useAnalysisStream } from "./hooks/useAnalysisStream";
import { buildTheme } from "./theme";
import type { AnalystReport } from "./types";

function isAnalystReport(data: { ticker: string }): data is AnalystReport {
  return "executive_summary" in data;
}

export default function App(): JSX.Element {
  const [darkMode, setDarkMode] = useState(false);
  const theme = useMemo(() => buildTheme(darkMode ? "dark" : "light"), [darkMode]);
  const { status, data, error, run } = useAnalysisStream();
  const busy = status === "connecting" || status === "running";

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
        <AppBar position="static" color="primary">
          <Toolbar>
            <InsightsIcon sx={{ mr: 1.5 }} />
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              Stock Fundamental Analyser
            </Typography>
            <IconButton color="inherit" onClick={() => setDarkMode((prev) => !prev)}>
              {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
            </IconButton>
          </Toolbar>
        </AppBar>
        <Container maxWidth="md">
          <Box sx={{ my: 4 }}>
            <Stack spacing={3}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
                  Run a fundamental analysis
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
                  Enter a ticker and pick a pipeline. Data streams live from the multi-agent
                  backend as each stage completes.
                </Typography>
                <TickerForm disabled={busy} onSubmit={run} />
              </Paper>
              <StatusBanner status={status} error={error} />
              {status === "done" && data && (isAnalystReport(data) ? <ReportCard report={data} /> : <RatiosCard ratios={data} />)}
            </Stack>
          </Box>
        </Container>
      </Box>
    </ThemeProvider>
  );
}
