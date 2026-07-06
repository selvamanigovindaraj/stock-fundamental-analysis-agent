from __future__ import annotations

import math

import pandas as pd
import pytest

from app.services.financial_sources import SourceUnavailableError
from app.services.financial_sources import yfinance_source


def _make_fake_ticker(*, missing_rows: list[str] | None = None, empty: bool = False) -> object:
    period = pd.Timestamp("2025-09-30")

    income_rows = {
        "Total Revenue": 416_161e6,
        "Cost Of Revenue": 220_960e6,
        "Gross Profit": 195_201e6,
        "Operating Income": 133_050e6,
        "Interest Expense": float("nan"),
        "Net Income": 112_010e6,
    }
    balance_rows = {
        "Current Assets": 147_957e6,
        "Inventory": 5_718e6,
        "Current Liabilities": 165_631e6,
        "Total Assets": 359_241e6,
        "Total Liabilities Net Minority Interest": 285_508e6,
        "Total Debt": 98_657e6,
        "Stockholders Equity": 73_733e6,
        "Cash And Cash Equivalents": 35_934e6,
    }
    cashflow_rows = {
        "Operating Cash Flow": 111_482e6,
        "Capital Expenditure": -12_715e6,
    }

    for row in missing_rows or []:
        for rows in (income_rows, balance_rows, cashflow_rows):
            rows.pop(row, None)

    def _df(rows: dict[str, float]) -> pd.DataFrame:
        if empty:
            return pd.DataFrame()
        return pd.DataFrame({period: rows})

    class FakeTicker:
        income_stmt = _df(income_rows)
        balance_sheet = _df(balance_rows)
        cashflow = _df(cashflow_rows)

    return FakeTicker()


@pytest.mark.asyncio
async def test_fetch_financials_normalizes_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_source.yf, "Ticker", lambda ticker: _make_fake_ticker())

    result = await yfinance_source.fetch_financials("AAPL")

    assert result.ticker == "AAPL"
    assert result.source == "yfinance"
    assert result.is_gaap is False
    assert result.income_statement.total_revenue == pytest.approx(416_161e6)
    assert result.income_statement.interest_expense == 0.0  # NaN normalized to 0.0
    assert result.balance_sheet.total_current_assets == pytest.approx(147_957e6)
    assert result.cash_flow.operating_cash_flow == pytest.approx(111_482e6)
    assert result.cash_flow.capital_expenditures == pytest.approx(12_715e6)  # sign normalized


@pytest.mark.asyncio
async def test_fetch_financials_raises_on_empty_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_source.yf, "Ticker", lambda ticker: _make_fake_ticker(empty=True))

    with pytest.raises(SourceUnavailableError):
        await yfinance_source.fetch_financials("NOPE")


@pytest.mark.asyncio
async def test_fetch_financials_raises_on_missing_required_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        yfinance_source.yf, "Ticker", lambda ticker: _make_fake_ticker(missing_rows=["Total Assets"])
    )

    with pytest.raises(SourceUnavailableError):
        await yfinance_source.fetch_financials("AAPL")


@pytest.mark.asyncio
async def test_fetch_financials_defaults_inventory_when_row_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A services company (e.g. META) genuinely carries no inventory row at all — that's a
    real zero, not missing data, and must not fail the whole source."""
    monkeypatch.setattr(
        yfinance_source.yf, "Ticker", lambda ticker: _make_fake_ticker(missing_rows=["Inventory"])
    )

    result = await yfinance_source.fetch_financials("META")

    assert result.balance_sheet.inventory == 0.0


@pytest.mark.asyncio
async def test_fetch_financials_handles_bank_shaped_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    """Banks (e.g. JPM) report no Cost Of Revenue/Gross Profit/Operating Income (net interest
    income model instead), no classified current/non-current balance sheet, and (confirmed
    live against real JPM data) no separate Capital Expenditure row at all — these rows are
    entirely absent, not zero, so the missing income fields must come back as NaN ("not
    applicable") while missing balance/cashflow fields safely default to 0.0 (already handled
    correctly downstream by RatioEngine's zero-denominator NaN check)."""
    monkeypatch.setattr(
        yfinance_source.yf,
        "Ticker",
        lambda ticker: _make_fake_ticker(
            missing_rows=[
                "Cost Of Revenue",
                "Gross Profit",
                "Operating Income",
                "Current Assets",
                "Current Liabilities",
                "Capital Expenditure",
            ]
        ),
    )

    result = await yfinance_source.fetch_financials("JPM")

    assert math.isnan(result.income_statement.cost_of_revenue)
    assert math.isnan(result.income_statement.gross_profit)
    assert math.isnan(result.income_statement.operating_income)
    assert result.balance_sheet.total_current_assets == 0.0
    assert result.balance_sheet.total_current_liabilities == 0.0
    assert result.cash_flow.capital_expenditures == 0.0
    assert result.income_statement.total_revenue == pytest.approx(416_161e6)  # unaffected fields still work
