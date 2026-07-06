from __future__ import annotations

import asyncio
import math
import re

import edgar
import pandas as pd

from app.config import get_settings
from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement
from app.services.financial_sources import SourceUnavailableError

_PERIOD_COL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_DEBT_CONCEPTS = ("ShortTermDebt", "CurrentPortionOfLongTermDebt", "LongTermDebt")


def _period_column(frame: pd.DataFrame) -> str:
    for column in frame.columns:
        if _PERIOD_COL_RE.match(str(column)):
            return str(column)
    raise SourceUnavailableError("edgartools statement has no recognizable period column")


def _find_concept_value(frame: pd.DataFrame, period_col: str, standard_concept: str) -> float | None:
    rows = frame[(frame["standard_concept"] == standard_concept) & ~frame["dimension"].astype(bool)]
    if rows.empty or pd.isna(rows.iloc[0][period_col]):
        return None
    return float(rows.iloc[0][period_col])


def _find_raw_concept_value(frame: pd.DataFrame, period_col: str, concept_suffix: str) -> float | None:
    rows = frame[(frame["concept"] == f"us-gaap_{concept_suffix}") & ~frame["dimension"].astype(bool)]
    if rows.empty or pd.isna(rows.iloc[0][period_col]):
        return None
    return float(rows.iloc[0][period_col])


def _find_total_revenue(income_df: pd.DataFrame, income_period: str) -> float | None:
    # For banks (e.g. JPM), edgartools' `standard_concept == "Revenue"` normalization
    # incorrectly maps to a narrow trading-revenue sub-line instead of true total revenue —
    # RevenuesNetOfInterestExpense (a bank's real total-revenue presentation) must be tried
    # first. Non-bank companies don't have this raw tag, so they fall through unaffected.
    for concept_suffix in ("RevenuesNetOfInterestExpense", "Revenues"):
        value = _find_raw_concept_value(income_df, income_period, concept_suffix)
        if value is not None:
            return value
    return _find_concept_value(income_df, income_period, "Revenue")


def _require_total_revenue(income_df: pd.DataFrame, income_period: str) -> float:
    value = _find_total_revenue(income_df, income_period)
    if value is None:
        raise SourceUnavailableError("edgartools statement missing concept: Revenue")
    return value


def _required_concept_value(frame: pd.DataFrame, period_col: str, standard_concept: str) -> float:
    value = _find_concept_value(frame, period_col, standard_concept)
    if value is None:
        raise SourceUnavailableError(f"edgartools statement missing concept: {standard_concept}")
    return value


def _optional_concept_value(
    frame: pd.DataFrame, period_col: str, standard_concept: str, *, default: float = 0.0
) -> float:
    value = _find_concept_value(frame, period_col, standard_concept)
    return default if value is None else value


async def fetch_financials(ticker: str) -> FinancialStatements:
    """Fetch and normalize income statement, balance sheet, and cash flow via edgartools."""

    def _fetch() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        edgar.set_identity(get_settings().sec_edgar_user_agent or "stock-fundamental-analyser research@example.com")
        financials = edgar.Company(ticker).get_financials()
        return (
            financials.income_statement().to_dataframe(),
            financials.balance_sheet().to_dataframe(),
            financials.cash_flow_statement().to_dataframe(),
        )

    try:
        income_df, balance_df, cashflow_df = await asyncio.to_thread(_fetch)
    except Exception as exc:  # noqa: BLE001 - any vendor failure means "try the next source"
        raise SourceUnavailableError(f"edgartools request failed: {exc}") from exc

    if income_df.empty or balance_df.empty or cashflow_df.empty:
        raise SourceUnavailableError("edgartools returned an empty statement")

    income_period = _period_column(income_df)
    balance_period = _period_column(balance_df)
    cashflow_period = _period_column(cashflow_df)

    total_debt = sum(
        _optional_concept_value(balance_df, balance_period, concept) for concept in _DEBT_CONCEPTS
    )

    return FinancialStatements(
        ticker=ticker,
        source="edgartools",
        is_gaap=True,
        income_statement=IncomeStatement(
            period_end=income_period.split(" ")[0],
            total_revenue=_require_total_revenue(income_df, income_period),
            # Banks (e.g. JPM) report no Cost Of Revenue/Gross Profit/Operating Income concept
            # at all (net interest income model instead) — NaN means "not applicable", not 0.
            cost_of_revenue=_optional_concept_value(
                income_df, income_period, "CostOfGoodsAndServicesSold", default=math.nan
            ),
            gross_profit=_optional_concept_value(income_df, income_period, "GrossProfit", default=math.nan),
            operating_income=_optional_concept_value(
                income_df, income_period, "OperatingIncomeLoss", default=math.nan
            ),
            interest_expense=_optional_concept_value(income_df, income_period, "InterestExpense"),
            net_income=_required_concept_value(income_df, income_period, "NetIncome"),
        ),
        balance_sheet=BalanceSheet(
            period_end=balance_period.split(" ")[0],
            # Banks use an unclassified balance sheet (no current/non-current split) — 0.0
            # here is safe because RatioEngine's zero-denominator check already converts
            # ratios dividing by total_current_liabilities to NaN.
            total_current_assets=_optional_concept_value(balance_df, balance_period, "CurrentAssetsTotal"),
            inventory=_optional_concept_value(balance_df, balance_period, "Inventories"),
            total_current_liabilities=_optional_concept_value(
                balance_df, balance_period, "CurrentLiabilitiesTotal"
            ),
            total_assets=_required_concept_value(balance_df, balance_period, "Assets"),
            total_liabilities=_required_concept_value(balance_df, balance_period, "Liabilities"),
            total_debt=total_debt,
            total_equity=_required_concept_value(balance_df, balance_period, "AllEquityBalance"),
            cash_and_equivalents=_optional_concept_value(
                balance_df, balance_period, "CashAndMarketableSecurities"
            ),
        ),
        cash_flow=CashFlowStatement(
            period_end=cashflow_period.split(" ")[0],
            operating_cash_flow=_required_concept_value(
                cashflow_df, cashflow_period, "NetCashFromOperatingActivities"
            ),
            capital_expenditures=_optional_concept_value(cashflow_df, cashflow_period, "CapitalExpenses"),
        ),
    )
