import type { JSX } from "react";
import { Box, Card, CardContent, CardHeader, Chip, Paper, Stack, Typography } from "@mui/material";
import type { FundamentalRatios } from "../types";

interface Stat {
  label: string;
  key: keyof FundamentalRatios;
  percent?: boolean;
}

const GROUPS: { title: string; stats: Stat[] }[] = [
  {
    title: "Liquidity",
    stats: [
      { label: "Current ratio", key: "current_ratio" },
      { label: "Quick ratio", key: "quick_ratio" },
      { label: "Operating cash flow ratio", key: "operating_cash_flow_ratio" },
    ],
  },
  {
    title: "Leverage",
    stats: [
      { label: "Debt to equity", key: "debt_to_equity" },
      { label: "Interest coverage", key: "interest_coverage" },
    ],
  },
  {
    title: "Profitability",
    stats: [
      { label: "Gross margin", key: "gross_margin", percent: true },
      { label: "Operating margin", key: "operating_margin", percent: true },
      { label: "Net margin", key: "net_margin", percent: true },
      { label: "ROE", key: "roe", percent: true },
      { label: "ROA", key: "roa", percent: true },
    ],
  },
  {
    title: "Efficiency & Cash Flow",
    stats: [
      { label: "Asset turnover", key: "asset_turnover" },
      { label: "Free cash flow", key: "free_cash_flow" },
    ],
  },
];

function formatValue(value: number | null, percent?: boolean): string {
  if (value === null || Number.isNaN(value)) {
    return "n/a";
  }
  if (percent) {
    return `${(value * 100).toFixed(1)}%`;
  }
  return Math.abs(value) >= 1_000_000 ? `$${(value / 1_000_000_000).toFixed(1)}B` : value.toFixed(2);
}

function StatTile({ stat, ratios }: { stat: Stat; ratios: FundamentalRatios }): JSX.Element {
  return (
    <Paper
      variant="outlined"
      sx={{ p: 1.5, flex: "1 1 160px", minWidth: 160 }}
    >
      <Typography variant="caption" color="text.secondary">
        {stat.label}
      </Typography>
      <Typography variant="h6">{formatValue(ratios[stat.key] as number | null, stat.percent)}</Typography>
    </Paper>
  );
}

export function RatiosCard({ ratios }: { ratios: FundamentalRatios }): JSX.Element {
  return (
    <Card>
      <CardHeader
        title={`${ratios.ticker} — Fundamental Ratios`}
        subheader={`Source: ${ratios.source}`}
        action={<Chip label={ratios.is_gaap ? "GAAP" : "Non-GAAP"} size="small" sx={{ mr: 2, mt: 1 }} />}
      />
      <CardContent>
        <Stack spacing={2.5}>
          {GROUPS.map((group) => (
            <Box key={group.title}>
              <Typography variant="subtitle2" color="primary" sx={{ mb: 1 }}>
                {group.title}
              </Typography>
              <Stack direction="row" spacing={1.5} sx={{ flexWrap: "wrap" }}>
                {group.stats.map((stat) => (
                  <StatTile key={stat.key} stat={stat} ratios={ratios} />
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
