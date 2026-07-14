from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.agents import ingestion_graph
from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement
from app.services.financial_sources import SourceUnavailableError
from app.services.financial_sources import sec_edgar_source, yfinance_source
from app.services import xbrl_cache


def _statements(source: str) -> FinancialStatements:
    return FinancialStatements(
        ticker="AAPL",
        source=source,  # type: ignore[arg-type]
        is_gaap=source != "yfinance",
        income_statement=IncomeStatement(
            period_end="2025-09-30",
            total_revenue=1.0,
            cost_of_revenue=1.0,
            gross_profit=1.0,
            operating_income=1.0,
            interest_expense=1.0,
            net_income=1.0,
        ),
        balance_sheet=BalanceSheet(
            period_end="2025-09-30",
            total_current_assets=1.0,
            inventory=1.0,
            total_current_liabilities=1.0,
            total_assets=1.0,
            total_liabilities=1.0,
            total_debt=1.0,
            total_equity=1.0,
            cash_and_equivalents=1.0,
        ),
        cash_flow=CashFlowStatement(period_end="2025-09-30", operating_cash_flow=1.0, capital_expenditures=1.0),
    )


@pytest.fixture(autouse=True)
def _mock_tracer(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake_tracer = MagicMock()
    monkeypatch.setattr(ingestion_graph, "_tracer", fake_tracer)
    return fake_tracer


@pytest.mark.asyncio
async def test_edgar_cache_success_short_circuits(
    monkeypatch: pytest.MonkeyPatch, _mock_tracer: MagicMock
) -> None:
    async def fake_fetch(ticker: str) -> FinancialStatements:
        return _statements("edgartools")

    monkeypatch.setattr(xbrl_cache, "fetch_financials", fake_fetch)

    result = await ingestion_graph.run_ingestion("AAPL")

    assert result.source == "edgartools"
    _mock_tracer.log_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_falls_through_to_sec_and_logs_once(
    monkeypatch: pytest.MonkeyPatch, _mock_tracer: MagicMock
) -> None:
    async def cache_fails(ticker: str) -> FinancialStatements:
        raise SourceUnavailableError("cache down")

    async def sec_succeeds(ticker: str) -> FinancialStatements:
        return _statements("sec_edgar")

    monkeypatch.setattr(xbrl_cache, "fetch_financials", cache_fails)
    monkeypatch.setattr(sec_edgar_source, "fetch_financials", sec_succeeds)

    result = await ingestion_graph.run_ingestion("AAPL")

    assert result.source == "sec_edgar"
    _mock_tracer.log_fallback.assert_called_once()
    call_kwargs = _mock_tracer.log_fallback.call_args.kwargs
    assert call_kwargs["from_source"] == "edgartools"
    assert call_kwargs["to_source"] == "sec_edgar"


@pytest.mark.asyncio
async def test_all_sources_fail_raises_and_logs_twice(
    monkeypatch: pytest.MonkeyPatch, _mock_tracer: MagicMock
) -> None:
    async def always_fails(ticker: str) -> FinancialStatements:
        raise SourceUnavailableError("nope")

    monkeypatch.setattr(yfinance_source, "fetch_financials", always_fails)
    monkeypatch.setattr(xbrl_cache, "fetch_financials", always_fails)
    monkeypatch.setattr(sec_edgar_source, "fetch_financials", always_fails)

    with pytest.raises(SourceUnavailableError):
        await ingestion_graph.run_ingestion("AAPL")

    assert _mock_tracer.log_fallback.call_count == 2


@pytest.mark.asyncio
async def test_partial_data_at_adapter_level_counts_as_failure(
    monkeypatch: pytest.MonkeyPatch, _mock_tracer: MagicMock
) -> None:
    """A source with a partial statement raises SourceUnavailableError (adapter-level
    contract) rather than returning a half-populated FinancialStatements — this falls
    through to the next tier exactly like a network failure would."""

    async def cache_partial(ticker: str) -> FinancialStatements:
        raise SourceUnavailableError("balance sheet missing required rows")

    async def sec_succeeds(ticker: str) -> FinancialStatements:
        return _statements("sec_edgar")

    monkeypatch.setattr(xbrl_cache, "fetch_financials", cache_partial)
    monkeypatch.setattr(sec_edgar_source, "fetch_financials", sec_succeeds)

    result = await ingestion_graph.run_ingestion("AAPL")

    assert result.source == "sec_edgar"


@pytest.mark.asyncio
async def test_yfinance_is_the_final_fallback(
    monkeypatch: pytest.MonkeyPatch, _mock_tracer: MagicMock
) -> None:
    async def fails(ticker: str) -> FinancialStatements:
        raise SourceUnavailableError("unavailable")

    async def yahoo_succeeds(ticker: str) -> FinancialStatements:
        return _statements("yfinance")

    monkeypatch.setattr(xbrl_cache, "fetch_financials", fails)
    monkeypatch.setattr(sec_edgar_source, "fetch_financials", fails)
    monkeypatch.setattr(yfinance_source, "fetch_financials", yahoo_succeeds)

    result = await ingestion_graph.run_ingestion("AAPL")

    assert result.source == "yfinance"
    assert _mock_tracer.log_fallback.call_count == 2
