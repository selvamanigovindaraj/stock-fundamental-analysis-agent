import type { JSX } from "react";
import { Alert, LinearProgress, Stack, Typography } from "@mui/material";

interface StatusBannerProps {
  status: "idle" | "connecting" | "running" | "done" | "error";
  error: string | null;
}

export function StatusBanner({ status, error }: StatusBannerProps): JSX.Element | null {
  if (status === "idle" || status === "done") {
    return null;
  }
  if (status === "error") {
    return <Alert severity="error">{error ?? "Something went wrong."}</Alert>;
  }
  return (
    <Stack spacing={1}>
      <Typography variant="body2" color="text.secondary">
        {status === "connecting" ? "Connecting…" : "Running agents…"}
      </Typography>
      <LinearProgress />
    </Stack>
  );
}
