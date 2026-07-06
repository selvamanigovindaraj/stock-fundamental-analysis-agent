from __future__ import annotations

import math

from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement

# Real line items pulled live from `yfinance` (Ticker.income_stmt / .balance_sheet / .cashflow,
# most recent fiscal-year column) on 2026-07-06 — not invented figures. Values in USD.
#
# AAPL's face income statement doesn't disclose "Interest Expense" as a separate line (it's
# folded into "Other Income/Expense, net"); yfinance reports it as NaN, normalized here to 0.0.
# That's a genuine real-world data-availability gap, not a contrived edge case — it's what
# drives AAPL's expected `interest_coverage` to NaN via the ratio engine's zero-division guard.
#
# `free_cash_flow` expected values are independently cross-checked: they match yfinance's own
# separately-reported "Free Cash Flow" row exactly for all three tickers (98,767M / 71,611M /
# 6,220M), which is a real external sanity check on the operating_cash_flow/capex inputs and
# the free_cash_flow formula, not just re-deriving the same number from the same formula twice.

AAPL_STATEMENTS = FinancialStatements(
    ticker="AAPL",
    source="yfinance",
    is_gaap=False,
    income_statement=IncomeStatement(
        period_end="2025-09-30",
        total_revenue=416_161e6,
        cost_of_revenue=220_960e6,
        gross_profit=195_201e6,
        operating_income=133_050e6,
        interest_expense=0.0,
        net_income=112_010e6,
    ),
    balance_sheet=BalanceSheet(
        period_end="2025-09-30",
        total_current_assets=147_957e6,
        inventory=5_718e6,
        total_current_liabilities=165_631e6,
        total_assets=359_241e6,
        total_liabilities=285_508e6,
        total_debt=98_657e6,
        total_equity=73_733e6,
        cash_and_equivalents=35_934e6,
    ),
    cash_flow=CashFlowStatement(
        period_end="2025-09-30",
        operating_cash_flow=111_482e6,
        capital_expenditures=12_715e6,
    ),
)

AAPL_EXPECTED_RATIOS = {
    "current_ratio": 0.893293,
    "quick_ratio": 0.858770,
    "debt_to_equity": 1.338030,
    "interest_coverage": math.nan,  # interest_expense unavailable on AAPL's face financials
    "gross_margin": 0.469052,
    "operating_margin": 0.319708,
    "net_margin": 0.269151,
    "roe": 1.519130,
    "roa": 0.311796,
    "asset_turnover": 1.158445,
    "free_cash_flow": 98_767e6,  # matches yfinance's own reported Free Cash Flow exactly
    "operating_cash_flow_ratio": 0.673074,
}

MSFT_STATEMENTS = FinancialStatements(
    ticker="MSFT",
    source="yfinance",
    is_gaap=False,
    income_statement=IncomeStatement(
        period_end="2025-06-30",
        total_revenue=281_724e6,
        cost_of_revenue=87_831e6,
        gross_profit=193_893e6,
        operating_income=128_528e6,
        interest_expense=2_385e6,
        net_income=101_832e6,
    ),
    balance_sheet=BalanceSheet(
        period_end="2025-06-30",
        total_current_assets=191_131e6,
        inventory=938e6,
        total_current_liabilities=141_218e6,
        total_assets=619_003e6,
        total_liabilities=275_524e6,
        total_debt=60_588e6,
        total_equity=343_479e6,
        cash_and_equivalents=30_242e6,
    ),
    cash_flow=CashFlowStatement(
        period_end="2025-06-30",
        operating_cash_flow=136_162e6,
        capital_expenditures=64_551e6,
    ),
)

MSFT_EXPECTED_RATIOS = {
    "current_ratio": 1.353446,
    "quick_ratio": 1.346804,
    "debt_to_equity": 0.176395,
    "interest_coverage": 53.890147,
    "gross_margin": 0.688237,
    "operating_margin": 0.456220,
    "net_margin": 0.361460,
    "roe": 0.296472,
    "roa": 0.164510,
    "asset_turnover": 0.455125,
    "free_cash_flow": 71_611e6,  # matches yfinance's own reported Free Cash Flow exactly
    "operating_cash_flow_ratio": 0.964197,
}

TSLA_STATEMENTS = FinancialStatements(
    ticker="TSLA",
    source="yfinance",
    is_gaap=False,
    income_statement=IncomeStatement(
        period_end="2025-12-31",
        total_revenue=94_827e6,
        cost_of_revenue=77_733e6,
        gross_profit=17_094e6,
        operating_income=4_849e6,
        interest_expense=338e6,
        net_income=3_794e6,
    ),
    balance_sheet=BalanceSheet(
        period_end="2025-12-31",
        total_current_assets=68_642e6,
        inventory=12_392e6,
        total_current_liabilities=31_714e6,
        total_assets=137_806e6,
        total_liabilities=54_941e6,
        total_debt=14_719e6,
        total_equity=82_137e6,
        cash_and_equivalents=16_513e6,
    ),
    cash_flow=CashFlowStatement(
        period_end="2025-12-31",
        operating_cash_flow=14_747e6,
        capital_expenditures=8_527e6,
    ),
)

TSLA_EXPECTED_RATIOS = {
    "current_ratio": 2.164407,
    "quick_ratio": 1.773665,
    "debt_to_equity": 0.179201,
    "interest_coverage": 14.346154,
    "gross_margin": 0.180265,
    "operating_margin": 0.051135,
    "net_margin": 0.040010,
    "roe": 0.046191,
    "roa": 0.027531,
    "asset_turnover": 0.688120,
    "free_cash_flow": 6_220e6,  # matches yfinance's own reported Free Cash Flow exactly
    "operating_cash_flow_ratio": 0.465000,
}

# JPM is a bank: its GAAP income statement has no Cost Of Revenue/Gross Profit/Operating
# Income concept at all (net interest income model instead), and no classified current/
# non-current balance sheet — these are NaN, not 0.0, because they're not applicable to how
# banks report, not a real zero (see app/services/financial_sources/*.py for the adapter-level
# fix). Real line items pulled live from yfinance on 2026-07-06.
JPM_STATEMENTS = FinancialStatements(
    ticker="JPM",
    source="yfinance",
    is_gaap=False,
    income_statement=IncomeStatement(
        period_end="2025-12-31",
        total_revenue=181_847e6,
        cost_of_revenue=math.nan,
        gross_profit=math.nan,
        operating_income=math.nan,
        interest_expense=97_898e6,
        net_income=57_048e6,
    ),
    balance_sheet=BalanceSheet(
        period_end="2025-12-31",
        total_current_assets=0.0,
        inventory=0.0,
        total_current_liabilities=0.0,
        total_assets=4_424_900e6,
        total_liabilities=4_062_462e6,
        total_debt=499_982e6,
        total_equity=362_438e6,
        cash_and_equivalents=343_338e6,
    ),
    cash_flow=CashFlowStatement(
        period_end="2025-12-31",
        operating_cash_flow=-147_782e6,  # legitimately negative for a bank under GAAP indirect method
        capital_expenditures=0.0,
    ),
)

JPM_EXPECTED_RATIOS = {
    "current_ratio": math.nan,  # no classified balance sheet for a bank
    "quick_ratio": math.nan,
    "debt_to_equity": 1.379497,
    "interest_coverage": math.nan,  # operating_income not applicable for a bank
    "gross_margin": math.nan,
    "operating_margin": math.nan,
    "net_margin": 0.313714,
    "roe": 0.157401,
    "roa": 0.012892,
    "asset_turnover": 0.041096,
    "free_cash_flow": -147_782e6,
    "operating_cash_flow_ratio": math.nan,
}

REFERENCE_CASES = [
    ("AAPL", AAPL_STATEMENTS, AAPL_EXPECTED_RATIOS),
    ("MSFT", MSFT_STATEMENTS, MSFT_EXPECTED_RATIOS),
    ("TSLA", TSLA_STATEMENTS, TSLA_EXPECTED_RATIOS),
    ("JPM", JPM_STATEMENTS, JPM_EXPECTED_RATIOS),
]
