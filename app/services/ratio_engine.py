from __future__ import annotations

import math

from app.models import FinancialStatements, FundamentalRatios


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return math.nan
    return numerator / denominator


class RatioEngine:
    """Computes fundamental ratios from financial statements."""

    @staticmethod
    def compute(statements: FinancialStatements) -> FundamentalRatios:
        """Pure computation of all ratios from an already-fetched FinancialStatements snapshot."""
        income = statements.income_statement
        balance = statements.balance_sheet
        cash_flow = statements.cash_flow

        free_cash_flow = cash_flow.operating_cash_flow - cash_flow.capital_expenditures

        return FundamentalRatios(
            ticker=statements.ticker,
            source=statements.source,
            is_gaap=statements.is_gaap,
            current_ratio=_safe_div(balance.total_current_assets, balance.total_current_liabilities),
            quick_ratio=_safe_div(
                balance.total_current_assets - balance.inventory, balance.total_current_liabilities
            ),
            debt_to_equity=_safe_div(balance.total_debt, balance.total_equity),
            interest_coverage=_safe_div(income.operating_income, income.interest_expense),
            gross_margin=_safe_div(income.gross_profit, income.total_revenue),
            operating_margin=_safe_div(income.operating_income, income.total_revenue),
            net_margin=_safe_div(income.net_income, income.total_revenue),
            roe=_safe_div(income.net_income, balance.total_equity),
            roa=_safe_div(income.net_income, balance.total_assets),
            asset_turnover=_safe_div(income.total_revenue, balance.total_assets),
            free_cash_flow=free_cash_flow,
            operating_cash_flow_ratio=_safe_div(
                cash_flow.operating_cash_flow, balance.total_current_liabilities
            ),
        )

    @staticmethod
    async def compute_all(ticker: str) -> FundamentalRatios:
        """Fetch financials for `ticker` via the ingestion subgraph, then compute ratios."""
        from app.agents.ingestion_graph import run_ingestion

        statements = await run_ingestion(ticker)
        return RatioEngine.compute(statements)
