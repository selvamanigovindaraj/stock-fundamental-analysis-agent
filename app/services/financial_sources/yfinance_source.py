from __future__ import annotations

import asyncio
import math

import pandas as pd
import yfinance as yf

from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement
from app.services.financial_sources import SourceUnavailableError

# Cost Of Revenue / Gross Profit / Operating Income are NOT required: banks (e.g. JPM) report
# a net-interest-income model with no such concepts at all, rather than a real zero. Same for
# Current Assets / Current Liabilities: banks use an unclassified balance sheet. Both are
# handled as optional below (NaN or 0.0 default, see fetch_financials).
_INCOME_ROWS = ("Total Revenue", "Interest Expense", "Net Income")
_BALANCE_ROWS = (
    "Total Assets",
    "Total Liabilities Net Minority Interest",
    "Total Debt",
    "Stockholders Equity",
    "Cash And Cash Equivalents",
)
# Capital Expenditure is NOT required either: banks (e.g. JPM) report no separate line for
# it at all — 0.0 is a safe default (free_cash_flow = operating_cash_flow - capex just
# reduces to operating_cash_flow, a reasonable approximation, not a misleading percentage).
_CASHFLOW_ROWS = ("Operating Cash Flow",)


def _latest_column(frame: pd.DataFrame, required_rows: tuple[str, ...]) -> pd.Series:
    if frame.empty:
        raise SourceUnavailableError("yfinance returned an empty statement")
    missing = [row for row in required_rows if row not in frame.index]
    if missing:
        raise SourceUnavailableError(f"yfinance statement missing rows: {missing}")
    return frame.iloc[:, 0]


def _value(series: pd.Series, row: str, *, default: float = 0.0) -> float:
    # Some companies genuinely have no value for a non-required row (e.g. services
    # companies carry no inventory at all) — absent or NaN both mean "0.0", not a failure.
    value = series.get(row, default)
    return default if pd.isna(value) else float(value)


async def fetch_financials(ticker: str) -> FinancialStatements:
    """Fetch and normalize income statement, balance sheet, and cash flow via yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker)
        income_frame, balance_frame, cashflow_frame = await asyncio.to_thread(
            lambda: (ticker_obj.income_stmt, ticker_obj.balance_sheet, ticker_obj.cashflow)
        )
    except Exception as exc:  # noqa: BLE001 - any vendor failure means "try the next source"
        raise SourceUnavailableError(f"yfinance request failed: {exc}") from exc

    income = _latest_column(income_frame, _INCOME_ROWS)
    balance = _latest_column(balance_frame, _BALANCE_ROWS)
    cash_flow = _latest_column(cashflow_frame, _CASHFLOW_ROWS)
    period_end = str(income.name.date())

    return FinancialStatements(
        ticker=ticker,
        source="yfinance",
        is_gaap=False,
        income_statement=IncomeStatement(
            period_end=period_end,
            total_revenue=_value(income, "Total Revenue"),
            cost_of_revenue=_value(income, "Cost Of Revenue", default=math.nan),
            gross_profit=_value(income, "Gross Profit", default=math.nan),
            operating_income=_value(income, "Operating Income", default=math.nan),
            interest_expense=_value(income, "Interest Expense"),
            net_income=_value(income, "Net Income"),
        ),
        balance_sheet=BalanceSheet(
            period_end=period_end,
            total_current_assets=_value(balance, "Current Assets"),
            inventory=_value(balance, "Inventory"),
            total_current_liabilities=_value(balance, "Current Liabilities"),
            total_assets=_value(balance, "Total Assets"),
            total_liabilities=_value(balance, "Total Liabilities Net Minority Interest"),
            total_debt=_value(balance, "Total Debt"),
            total_equity=_value(balance, "Stockholders Equity"),
            cash_and_equivalents=_value(balance, "Cash And Cash Equivalents"),
        ),
        cash_flow=CashFlowStatement(
            period_end=period_end,
            operating_cash_flow=_value(cash_flow, "Operating Cash Flow"),
            capital_expenditures=_value(cash_flow, "Capital Expenditure"),
        ),
    )
