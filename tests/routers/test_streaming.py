from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement
from app.routers import streaming
from app.services.financial_sources import SourceUnavailableError
from app.services.ratio_engine import RatioEngine


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


def test_stream_analysis_returns_result_event_on_success(
    monkeypatch: pytest.MonkeyPatch, fake_lifespan_postgres: None
) -> None:
    statements = _statements()
    expected_ratios = RatioEngine.compute(statements)

    async def fake_run_supervisor_analysis(ticker: str) -> dict[str, object]:
        return {"ticker": ticker, "financials": statements, "ratios": expected_ratios, "messages": [], "errors": []}

    monkeypatch.setattr(streaming, "run_supervisor_analysis", fake_run_supervisor_analysis)

    with TestClient(app) as client:
        response = client.get("/analysis/AAPL/stream")

    assert response.status_code == 200
    assert "event: started" in response.text
    assert "event: result" in response.text
    assert '"ticker":"AAPL"' in response.text


def test_stream_analysis_returns_error_event_on_source_unavailable(
    monkeypatch: pytest.MonkeyPatch, fake_lifespan_postgres: None
) -> None:
    async def fake_run_supervisor_analysis(ticker: str) -> dict[str, object]:
        raise SourceUnavailableError(f"{ticker}: all sources failed")

    monkeypatch.setattr(streaming, "run_supervisor_analysis", fake_run_supervisor_analysis)

    with TestClient(app) as client:
        response = client.get("/analysis/BADTICKER/stream")

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "all sources failed" in response.text


def test_stream_fundamentals_returns_result_event_on_success(
    monkeypatch: pytest.MonkeyPatch, fake_lifespan_postgres: None
) -> None:
    statements = _statements()
    expected_ratios = RatioEngine.compute(statements)

    async def fake_compute_all(ticker: str) -> object:
        return expected_ratios

    monkeypatch.setattr(RatioEngine, "compute_all", staticmethod(fake_compute_all))

    with TestClient(app) as client:
        response = client.get("/fundamentals/AAPL/stream")

    assert response.status_code == 200
    assert "event: started" in response.text
    assert "event: result" in response.text
