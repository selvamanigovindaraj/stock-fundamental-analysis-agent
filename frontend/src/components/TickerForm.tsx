import { useState } from "react";
import type { JSX } from "react";
import { Button, MenuItem, Stack, TextField } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import type { Pipeline } from "../types";

const PIPELINE_OPTIONS: { value: Pipeline; label: string }[] = [
  { value: "fundamentals", label: "Fundamentals (ratios only)" },
  { value: "analysis", label: "Analysis (supervisor-routed ratios)" },
  { value: "report", label: "Full analyst report (5-agent team)" },
];

interface TickerFormProps {
  disabled: boolean;
  onSubmit: (pipeline: Pipeline, ticker: string) => void;
}

export function TickerForm({ disabled, onSubmit }: TickerFormProps): JSX.Element {
  const [ticker, setTicker] = useState("");
  const [pipeline, setPipeline] = useState<Pipeline>("report");

  const trimmed = ticker.trim();

  return (
    <Stack
      component="form"
      direction={{ xs: "column", sm: "row" }}
      spacing={2}
      onSubmit={(event) => {
        event.preventDefault();
        if (trimmed) {
          onSubmit(pipeline, trimmed);
        }
      }}
    >
      <TextField
        label="Ticker"
        placeholder="e.g. AAPL"
        value={ticker}
        onChange={(event) => setTicker(event.target.value)}
        disabled={disabled}
        fullWidth
      />
      <TextField
        select
        label="Pipeline"
        value={pipeline}
        onChange={(event) => setPipeline(event.target.value as Pipeline)}
        disabled={disabled}
        sx={{ minWidth: 280 }}
      >
        {PIPELINE_OPTIONS.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
      <Button
        type="submit"
        variant="contained"
        startIcon={<SearchIcon />}
        disabled={disabled || !trimmed}
        sx={{ minWidth: 140 }}
      >
        Analyze
      </Button>
    </Stack>
  );
}
