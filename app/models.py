from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CRITIC_QUALITY_THRESHOLD = 0.80
INVESTMENT_DISCLAIMER = (
    "This report is generated for informational purposes only and does not constitute "
    "financial advice. Consult a licensed financial advisor before making investment "
    "decisions."
)


class Document(BaseModel):
    """A retrieved or ingested document chunk."""

    id: str
    content: str
    metadata: dict[str, str] = {}


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Outgoing chat response body."""

    message: str
    sources: list[Document] = []
    conversation_id: str


class IncomeStatement(BaseModel):
    """A single-period income statement."""

    period_end: str
    total_revenue: float
    cost_of_revenue: float
    gross_profit: float
    operating_income: float
    interest_expense: float
    net_income: float


class BalanceSheet(BaseModel):
    """A single-period balance sheet."""

    period_end: str
    total_current_assets: float
    inventory: float
    total_current_liabilities: float
    total_assets: float
    total_liabilities: float
    total_debt: float
    total_equity: float
    cash_and_equivalents: float


class CashFlowStatement(BaseModel):
    """A single-period cash flow statement."""

    period_end: str
    operating_cash_flow: float
    capital_expenditures: float

    @field_validator("capital_expenditures")
    @classmethod
    def _positive_magnitude(cls, v: float) -> float:
        return abs(v)


class FinancialStatements(BaseModel):
    """Normalized income statement, balance sheet, and cash flow statement for a ticker."""

    ticker: str
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow: CashFlowStatement
    source: Literal["yfinance", "edgartools", "sec_edgar"]
    # True for edgartools/sec_edgar (direct XBRL us-gaap tags); False for yfinance, since
    # Yahoo reclassifies/normalizes line items away from as-filed GAAP presentation.
    # is_gaap=False results may diverge from as-filed GAAP for companies emphasizing
    # adjusted/non-GAAP metrics; prefer an is_gaap=True source for strict GAAP compliance.
    is_gaap: bool


class FilingDocument(BaseModel):
    """A single extracted section (MD&A or Risk Factors) from one 10-K/10-Q filing."""

    ticker: str
    form_type: Literal["10-K", "10-Q"]
    period: str
    accession_no: str
    filing_url: str
    section: Literal["mdna", "risk_factors"]
    text: str


class Chunk(BaseModel):
    """A single chunk of a FilingDocument, ready for embedding."""

    text: str
    ticker: str
    form_type: Literal["10-K", "10-Q"]
    period: str
    section: Literal["mdna", "risk_factors"]
    accession_no: str
    filing_url: str
    chunk_index: int


class FilingsRAGAnswer(BaseModel):
    """Answer to a natural-language question about a company's filings, with citations."""

    answer: str
    citations: list[Document] = []


class FundamentalRatios(BaseModel):
    """Fundamental ratios computed from a FinancialStatements snapshot."""

    ticker: str
    source: Literal["yfinance", "edgartools", "sec_edgar"]
    is_gaap: bool
    current_ratio: float
    quick_ratio: float
    debt_to_equity: float
    interest_coverage: float
    gross_margin: float
    operating_margin: float
    net_margin: float
    roe: float
    roa: float
    asset_turnover: float
    free_cash_flow: float
    operating_cash_flow_ratio: float


class ArticleSentiment(BaseModel):
    """LLM-scored sentiment for a single news article."""

    title: str
    url: str
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=0.0, le=1.0)  # 0.0 (most negative) .. 1.0 (most positive)


class NewsSentimentResult(BaseModel):
    """Aggregated sentiment across a ticker's recent news, with per-article detail."""

    ticker: str
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=0.0, le=1.0)  # same 0.0-1.0 scale as ArticleSentiment
    key_themes: list[str]
    articles: list[ArticleSentiment]


class SectorBenchmark(BaseModel):
    """Live-fetched sector-peer median P/E, P/B, and ROE for a ticker's sector."""

    sector: str
    median_pe: float | None
    median_pb: float | None
    median_roe: float | None
    peers_used: list[str]
    errors: list[str] = []


class ValuationResult(BaseModel):
    """A ticker's valuation verdict vs. its sector-peer benchmark."""

    ticker: str
    valuation_verdict: Literal["undervalued", "fairly_valued", "overvalued", "insufficient_data"]
    vs_sector: dict[str, float | None]  # keys: "pe", "pb", "roe" -> ticker/sector-median ratio
    risk_flags: list[str]


class CriticReview(BaseModel):
    """Structured LLM-as-judge review of an analyst report draft."""

    score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["accept", "revise"]
    revision_instructions: str = ""


def _coerce_str_list(value: object) -> object:
    # DeepSeek's structured output occasionally returns a JSON-stringified array or a
    # numbered/bulleted multiline string instead of a real list for these fields (found via
    # live verify-agent: 5/10 real ticker reports hit this and crashed after ~20s of prior
    # agent work) -- tolerate the common shapes rather than hard-failing the whole report.
    if value is None:
        return []
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) > 1:
        # Only strip an actual bullet ("-"/"*") or a number followed by "." or ")" -- the
        # original `^[-*\d]+[.)]?\s*` pattern also matched leading digits with no delimiter
        # at all, corrupting text like "10-K reports..." into "K reports..." (caught in PR
        # review).
        return [re.sub(r"^(?:[-*]\s*|\d+[.)]\s*)", "", line) for line in lines]
    return [stripped]


class AnalystReport(BaseModel):
    """Final structured analyst report produced by the Report-Writer agent."""

    ticker: str
    executive_summary: str
    financial_health: str
    valuation_assessment: str
    risk_factors: list[str]
    key_themes: list[str]
    disclaimer: str

    @field_validator("risk_factors", "key_themes", mode="before")
    @classmethod
    def _coerce_list_fields(cls, v: object) -> object:
        return _coerce_str_list(v)
