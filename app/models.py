from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


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
