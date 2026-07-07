from __future__ import annotations

import pytest

from app.agents import ratio_analysis_graph
from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement


def _statements() -> FinancialStatements:
    return FinancialStatements(
        ticker="AAPL",
        source="yfinance",
        is_gaap=False,
        income_statement=IncomeStatement(
            period_end="2025-09-30",
            total_revenue=100.0,
            cost_of_revenue=40.0,
            gross_profit=60.0,
            operating_income=30.0,
            interest_expense=2.0,
            net_income=20.0,
        ),
        balance_sheet=BalanceSheet(
            period_end="2025-09-30",
            total_current_assets=50.0,
            inventory=10.0,
            total_current_liabilities=25.0,
            total_assets=200.0,
            total_liabilities=80.0,
            total_debt=60.0,
            total_equity=120.0,
            cash_and_equivalents=15.0,
        ),
        cash_flow=CashFlowStatement(
            period_end="2025-09-30", operating_cash_flow=35.0, capital_expenditures=5.0
        ),
    )


@pytest.mark.asyncio
async def test_run_ratio_analysis_computes_ratios_matching_ratio_engine() -> None:
    from app.services.ratio_engine import RatioEngine

    statements = _statements()

    result = await ratio_analysis_graph.run_ratio_analysis(statements)

    assert result == RatioEngine.compute(statements)
