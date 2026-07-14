export type Pipeline = "fundamentals" | "analysis" | "report";

export interface FundamentalRatios {
  ticker: string;
  source: "yfinance" | "edgartools" | "sec_edgar";
  is_gaap: boolean;
  current_ratio: number | null;
  quick_ratio: number | null;
  debt_to_equity: number;
  interest_coverage: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number;
  roe: number;
  roa: number;
  asset_turnover: number;
  free_cash_flow: number;
  operating_cash_flow_ratio: number | null;
}

export interface AnalystReport {
  ticker: string;
  executive_summary: string;
  financial_health: string;
  valuation_assessment: string;
  risk_factors: string[];
  key_themes: string[];
  disclaimer: string;
}

export type StreamResult = FundamentalRatios | AnalystReport;

export type SSEEvent =
  | { type: "started"; ticker: string }
  | { type: "result"; data: StreamResult }
  | { type: "error"; ticker: string; error: string };
