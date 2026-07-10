import type { JSX } from "react";
import { Alert, Card, CardContent, CardHeader, Chip, Divider, Stack, Typography } from "@mui/material";
import type { AnalystReport } from "../types";

function Section({ title, body }: { title: string; body: string }): JSX.Element {
  return (
    <Stack spacing={0.5}>
      <Typography variant="subtitle2" color="primary">
        {title}
      </Typography>
      <Typography variant="body2">{body}</Typography>
    </Stack>
  );
}

export function ReportCard({ report }: { report: AnalystReport }): JSX.Element {
  return (
    <Card variant="outlined">
      <CardHeader title={`${report.ticker} — Analyst Report`} />
      <CardContent>
        <Stack spacing={2}>
          <Section title="Executive Summary" body={report.executive_summary} />
          <Section title="Financial Health" body={report.financial_health} />
          <Section title="Valuation" body={report.valuation_assessment} />
          {report.risk_factors.length > 0 && (
            <Stack spacing={1}>
              <Typography variant="subtitle2" color="primary">
                Risk Factors
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                {report.risk_factors.map((factor) => (
                  <Chip key={factor} label={factor} color="warning" variant="outlined" size="small" />
                ))}
              </Stack>
            </Stack>
          )}
          {report.key_themes.length > 0 && (
            <Stack spacing={1}>
              <Typography variant="subtitle2" color="primary">
                Key Themes
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                {report.key_themes.map((theme) => (
                  <Chip key={theme} label={theme} color="info" variant="outlined" size="small" />
                ))}
              </Stack>
            </Stack>
          )}
          <Divider />
          <Alert severity="info" variant="outlined">
            {report.disclaimer}
          </Alert>
        </Stack>
      </CardContent>
    </Card>
  );
}
