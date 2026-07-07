from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agents import analyst_team_graph
from app.models import (
    AnalystReport,
    ArticleSentiment,
    FinancialStatements,
    FundamentalRatios,
    NewsSentimentResult,
    ValuationResult,
)
from app.services.financial_sources import SourceUnavailableError
from tests.conftest import make_financial_statements


def _financials() -> FinancialStatements:
    return make_financial_statements()


def _ratios() -> FundamentalRatios:
    return FundamentalRatios(
        ticker="AAPL",
        source="yfinance",
        is_gaap=False,
        current_ratio=2.0,
        quick_ratio=1.6,
        debt_to_equity=0.5,
        interest_coverage=15.0,
        gross_margin=0.6,
        operating_margin=0.3,
        net_margin=0.2,
        roe=0.17,
        roa=0.1,
        asset_turnover=0.5,
        free_cash_flow=30.0,
        operating_cash_flow_ratio=1.4,
    )


def _sentiment() -> NewsSentimentResult:
    return NewsSentimentResult(
        ticker="AAPL",
        sentiment="positive",
        score=0.7,
        key_themes=["earnings beat"],
        articles=[ArticleSentiment(title="t", url="u", sentiment="positive", score=0.7)],
    )


def _valuation() -> ValuationResult:
    return ValuationResult(
        ticker="AAPL",
        valuation_verdict="fairly_valued",
        vs_sector={"pe": 1.0, "pb": 1.0, "roe": 1.0},
        risk_flags=[],
    )


def _report() -> AnalystReport:
    return AnalystReport(
        ticker="AAPL",
        executive_summary="ok",
        financial_health="ok",
        valuation_assessment="ok",
        risk_factors=[],
        key_themes=[],
        disclaimer="ok",
    )


@pytest.fixture(autouse=True)
def _init_with_in_memory_checkpointer(monkeypatch: pytest.MonkeyPatch) -> None:
    analyst_team_graph.init_analyst_team_graph(InMemorySaver())
    yield
    monkeypatch.setattr(analyst_team_graph, "_compiled_graph", None)


@pytest.mark.asyncio
async def test_fan_out_dispatches_both_branches_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        calls.append("financials")
        return {
            "ticker": ticker,
            "financials": _financials(),
            "ratios": _ratios(),
            "messages": [],
            "errors": [],
        }

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        calls.append("news")
        return _sentiment()

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return _valuation()

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        return _report()

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)

    result = await analyst_team_graph.run_team_analysis("AAPL")

    assert set(calls) == {"financials", "news"}
    assert result["financials"] == _financials()
    assert result["sentiment"] == _sentiment()
    assert result["valuation"] == _valuation()
    assert result["report"] == _report()


@pytest.mark.asyncio
async def test_financials_branch_failure_does_not_block_the_rest_of_the_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        raise SourceUnavailableError(f"{ticker}: all sources failed")

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        return _sentiment()

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return _valuation()

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        return _report()

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)

    result = await analyst_team_graph.run_team_analysis("AAPL")

    assert result["financials"] is None
    assert result["ratios"] is None
    assert any("all sources failed" in e for e in result["errors"])
    assert result["sentiment"] == _sentiment()
    assert result["report"] == _report()  # pipeline still reaches the end


@pytest.mark.asyncio
async def test_both_branches_degraded_still_reaches_report_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        raise SourceUnavailableError(f"{ticker}: all sources failed")

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        # news_sentiment_graph never raises by design -- it degrades to neutral itself.
        return NewsSentimentResult(
            ticker=ticker, sentiment="neutral", score=0.5, key_themes=[], articles=[]
        )

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return ValuationResult(
            ticker=ticker,
            valuation_verdict="insufficient_data",
            vs_sector={"pe": None, "pb": None, "roe": None},
            risk_flags=[],
        )

    report_calls: list[dict[str, object]] = []

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        report_calls.append(kwargs)
        return _report()

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)

    result = await analyst_team_graph.run_team_analysis("AAPL")

    assert result["report"] == _report()
    assert report_calls[0]["financials"] is None
    assert report_calls[0]["sentiment"].sentiment == "neutral"
