from __future__ import annotations

import math

import pandas as pd
import pytest

from app.services.financial_sources import SourceUnavailableError
from app.services.financial_sources import edgartools_source

_PERIOD = "2025-09-27 (FY)"


def _statement_df(rows: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"concept": f"us-gaap_{concept}", "standard_concept": concept, "dimension": False, _PERIOD: value}
            for concept, value in rows.items()
        ]
    )


def _make_fake_company(*, empty: bool = False, missing_concepts: list[str] | None = None) -> object:
    income_rows = {
        "Revenue": 416_161e6,
        "CostOfGoodsAndServicesSold": 220_960e6,
        "GrossProfit": 195_201e6,
        "OperatingIncomeLoss": 133_050e6,
        "NetIncome": 112_010e6,
    }
    balance_rows = {
        "CurrentAssetsTotal": 147_957e6,
        "Inventories": 5_718e6,
        "CurrentLiabilitiesTotal": 165_631e6,
        "Assets": 359_241e6,
        "Liabilities": 285_508e6,
        "AllEquityBalance": 73_733e6,
        "CashAndMarketableSecurities": 35_934e6,
        "ShortTermDebt": 7_979e6,
        "CurrentPortionOfLongTermDebt": 12_350e6,
        "LongTermDebt": 78_328e6,
    }
    cashflow_rows = {
        "NetCashFromOperatingActivities": 111_482e6,
        "CapitalExpenses": -12_715e6,
    }

    for concept in missing_concepts or []:
        for rows in (income_rows, balance_rows, cashflow_rows):
            rows.pop(concept, None)

    def _df(rows: dict[str, float]) -> pd.DataFrame:
        return pd.DataFrame() if empty else _statement_df(rows)

    class FakeFinancials:
        def income_statement(self) -> object:
            return type("S", (), {"to_dataframe": lambda self: _df(income_rows)})()

        def balance_sheet(self) -> object:
            return type("S", (), {"to_dataframe": lambda self: _df(balance_rows)})()

        def cash_flow_statement(self) -> object:
            return type("S", (), {"to_dataframe": lambda self: _df(cashflow_rows)})()

    class FakeCompany:
        def get_financials(self) -> FakeFinancials:
            return FakeFinancials()

    return FakeCompany()


@pytest.mark.asyncio
async def test_fetch_financials_normalizes_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edgartools_source.edgar, "Company", lambda ticker: _make_fake_company())
    monkeypatch.setattr(edgartools_source.edgar, "set_identity", lambda identity: None)

    result = await edgartools_source.fetch_financials("AAPL")

    assert result.ticker == "AAPL"
    assert result.source == "edgartools"
    assert result.is_gaap is True
    assert result.income_statement.total_revenue == pytest.approx(416_161e6)
    assert result.income_statement.interest_expense == 0.0  # missing concept defaults to 0.0
    assert result.balance_sheet.total_current_assets == pytest.approx(147_957e6)
    assert result.balance_sheet.total_debt == pytest.approx(98_657e6)  # sum of the 3 debt concepts
    assert result.cash_flow.operating_cash_flow == pytest.approx(111_482e6)
    assert result.cash_flow.capital_expenditures == pytest.approx(12_715e6)  # sign normalized


@pytest.mark.asyncio
async def test_fetch_financials_raises_on_empty_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edgartools_source.edgar, "Company", lambda ticker: _make_fake_company(empty=True))
    monkeypatch.setattr(edgartools_source.edgar, "set_identity", lambda identity: None)

    with pytest.raises(SourceUnavailableError):
        await edgartools_source.fetch_financials("NOPE")


@pytest.mark.asyncio
async def test_fetch_financials_raises_on_missing_required_concept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        edgartools_source.edgar,
        "Company",
        lambda ticker: _make_fake_company(missing_concepts=["Assets"]),
    )
    monkeypatch.setattr(edgartools_source.edgar, "set_identity", lambda identity: None)

    with pytest.raises(SourceUnavailableError):
        await edgartools_source.fetch_financials("AAPL")


@pytest.mark.asyncio
async def test_fetch_financials_handles_bank_shaped_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    """Banks (e.g. JPM) have no GrossProfit/OperatingIncomeLoss/CostOfRevenue concept and no
    classified current/non-current balance sheet at all in SEC XBRL — missing income fields
    must come back as NaN ("not applicable"), missing balance fields safely default to 0.0."""
    monkeypatch.setattr(
        edgartools_source.edgar,
        "Company",
        lambda ticker: _make_fake_company(
            missing_concepts=[
                "CostOfGoodsAndServicesSold",
                "GrossProfit",
                "OperatingIncomeLoss",
                "CurrentAssetsTotal",
                "CurrentLiabilitiesTotal",
            ]
        ),
    )
    monkeypatch.setattr(edgartools_source.edgar, "set_identity", lambda identity: None)

    result = await edgartools_source.fetch_financials("JPM")

    assert math.isnan(result.income_statement.cost_of_revenue)
    assert math.isnan(result.income_statement.gross_profit)
    assert math.isnan(result.income_statement.operating_income)
    assert result.balance_sheet.total_current_assets == 0.0
    assert result.balance_sheet.total_current_liabilities == 0.0
    assert result.income_statement.total_revenue == pytest.approx(416_161e6)


@pytest.mark.asyncio
async def test_fetch_financials_prefers_revenues_net_of_interest_expense_for_banks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """For real JPM data, edgartools' `standard_concept == "Revenue"` normalization
    incorrectly maps to `PrincipalTransactionsRevenue` (~$27B, one narrow trading-revenue
    line) instead of true total revenue (~$182B) — inflating net_margin past 100%. The raw
    `RevenuesNetOfInterestExpense` concept (a bank's real total-revenue presentation) must be
    preferred over the unreliable `standard_concept` label when both are present."""
    income_rows = pd.DataFrame(
        [
            {
                "concept": "us-gaap_PrincipalTransactionsRevenue",
                "standard_concept": "Revenue",  # misleadingly labeled by edgartools for banks
                "dimension": False,
                _PERIOD: 27_212e6,
            },
            {
                "concept": "us-gaap_RevenuesNetOfInterestExpense",
                "standard_concept": None,  # the real total-revenue tag, unlabeled by edgartools
                "dimension": False,
                _PERIOD: 182_447e6,
            },
            {"concept": "us-gaap_NetIncomeLoss", "standard_concept": "NetIncome", "dimension": False, _PERIOD: 57_048e6},
        ]
    )

    base_company = _make_fake_company()
    base_financials = base_company.get_financials()

    class FakeFinancials:
        def income_statement(self) -> object:
            return type("S", (), {"to_dataframe": lambda self: income_rows})()

        def balance_sheet(self) -> object:
            return base_financials.balance_sheet()

        def cash_flow_statement(self) -> object:
            return base_financials.cash_flow_statement()

    monkeypatch.setattr(
        edgartools_source.edgar,
        "Company",
        lambda ticker: type("C", (), {"get_financials": lambda self: FakeFinancials()})(),
    )
    monkeypatch.setattr(edgartools_source.edgar, "set_identity", lambda identity: None)

    result = await edgartools_source.fetch_financials("JPM")

    assert result.income_statement.total_revenue == pytest.approx(182_447e6)
