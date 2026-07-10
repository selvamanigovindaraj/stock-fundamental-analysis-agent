import type { JSX } from "react";
import { Card, CardContent, CardHeader, Chip, Table, TableBody, TableCell, TableRow } from "@mui/material";
import type { FundamentalRatios } from "../types";

const ROWS: { label: string; key: keyof FundamentalRatios; percent?: boolean }[] = [
  { label: "Current ratio", key: "current_ratio" },
  { label: "Quick ratio", key: "quick_ratio" },
  { label: "Debt to equity", key: "debt_to_equity" },
  { label: "Interest coverage", key: "interest_coverage" },
  { label: "Gross margin", key: "gross_margin", percent: true },
  { label: "Operating margin", key: "operating_margin", percent: true },
  { label: "Net margin", key: "net_margin", percent: true },
  { label: "ROE", key: "roe", percent: true },
  { label: "ROA", key: "roa", percent: true },
  { label: "Asset turnover", key: "asset_turnover" },
  { label: "Free cash flow", key: "free_cash_flow" },
  { label: "Operating cash flow ratio", key: "operating_cash_flow_ratio" },
];

function formatValue(value: number | null, percent?: boolean): string {
  if (value === null || Number.isNaN(value)) {
    return "n/a";
  }
  return percent ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
}

export function RatiosCard({ ratios }: { ratios: FundamentalRatios }): JSX.Element {
  return (
    <Card variant="outlined">
      <CardHeader
        title={`${ratios.ticker} — Fundamental Ratios`}
        subheader={`Source: ${ratios.source}`}
        action={<Chip label={ratios.is_gaap ? "GAAP" : "Non-GAAP"} size="small" sx={{ mr: 2, mt: 1 }} />}
      />
      <CardContent>
        <Table size="small">
          <TableBody>
            {ROWS.map((row) => (
              <TableRow key={row.key}>
                <TableCell>{row.label}</TableCell>
                <TableCell align="right">{formatValue(ratios[row.key] as number | null, row.percent)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
