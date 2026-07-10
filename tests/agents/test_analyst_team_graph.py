from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agents import analyst_team_graph
from app.models import (
    AnalystReport,
    ArticleSentiment,
    CriticReview,
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

    async def fake_run_report_critic(**kwargs: object) -> CriticReview:
        return CriticReview(score=0.9, verdict="accept", revision_instructions="")

    monkeypatch.setattr(analyst_team_graph, "run_report_critic", fake_run_report_critic)
    yield
    monkeypatch.setattr(analyst_team_graph, "_compiled_graph", None)


class _FakeCompiledTeamGraph:
    def __init__(self) -> None:
        self.captured_config: dict[str, object] | None = None

    async def ainvoke(self, state: object, config: dict[str, object]) -> dict[str, object]:
        self.captured_config = config
        return {
            "ticker": "AAPL",
            "financials": None,
            "ratios": None,
            "sentiment": None,
            "valuation": None,
            "report": _report(),
            "messages": [],
            "errors": [],
        }


@pytest.mark.asyncio
async def test_run_team_analysis_defaults_to_unique_thread_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_graph = _FakeCompiledTeamGraph()
    monkeypatch.setattr(analyst_team_graph, "_compiled_graph", fake_graph)

    await analyst_team_graph.run_team_analysis("AAPL")
    assert fake_graph.captured_config is not None
    first_thread_id = fake_graph.captured_config["configurable"]["thread_id"]

    await analyst_team_graph.run_team_analysis("AAPL")
    assert fake_graph.captured_config is not None
    second_thread_id = fake_graph.captured_config["configurable"]["thread_id"]

    assert first_thread_id.startswith("AAPL:team:")
    assert second_thread_id.startswith("AAPL:team:")
    assert first_thread_id != second_thread_id


@pytest.mark.asyncio
async def test_run_team_analysis_accepts_thread_id_and_config_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A static thread_id (f"{ticker}:team") would make concurrent/repeated runs for the
    same ticker share/overwrite the same checkpoint thread in the shared checkpointer --
    callers must be able to override it, and pass their own config through (e.g. for
    tracing metadata), matching run_supervisor_analysis's own design (caught in PR review)."""
    fake_graph = _FakeCompiledTeamGraph()
    monkeypatch.setattr(analyst_team_graph, "_compiled_graph", fake_graph)

    caller_config = {"callbacks": ["fake-callback"], "configurable": {"other_key": "x"}}
    await analyst_team_graph.run_team_analysis(
        "AAPL", thread_id="custom-thread", config=caller_config
    )

    assert fake_graph.captured_config is not None
    assert fake_graph.captured_config["callbacks"] == ["fake-callback"]
    assert fake_graph.captured_config["configurable"]["other_key"] == "x"
    assert fake_graph.captured_config["configurable"]["thread_id"] == "custom-thread"


@pytest.mark.asyncio
async def test_financials_branch_uses_parent_thread_id_for_nested_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_thread_id = ""

    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        nonlocal captured_thread_id
        captured_thread_id = thread_id or ""
        return {
            "ticker": ticker,
            "financials": _financials(),
            "ratios": _ratios(),
            "messages": [],
            "errors": [],
        }

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)

    await analyst_team_graph._financials_branch(
        {
            "ticker": "AAPL",
            "financials": None,
            "ratios": None,
            "sentiment": None,
            "valuation": None,
            "report": None,
            "messages": [],
            "errors": [],
        },
        {"configurable": {"thread_id": "team-thread"}},
    )

    assert captured_thread_id == "team-thread:financials"


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


@pytest.mark.asyncio
async def test_critic_loop_revises_once_then_accepts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        return {
            "ticker": ticker,
            "financials": _financials(),
            "ratios": _ratios(),
            "messages": [],
            "errors": [],
        }

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        return _sentiment()

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return _valuation()

    report_calls: list[object] = []

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        report_calls.append(kwargs.get("revision_instructions"))
        return _report().model_copy(update={"executive_summary": f"draft {len(report_calls)}"})

    reviews = [
        CriticReview(score=0.5, verdict="revise", revision_instructions="Fix citations."),
        CriticReview(score=0.9, verdict="accept", revision_instructions=""),
    ]

    async def fake_run_report_critic(**kwargs: object) -> CriticReview:
        return reviews.pop(0)

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)
    monkeypatch.setattr(analyst_team_graph, "run_report_critic", fake_run_report_critic)

    result = await analyst_team_graph.run_team_analysis("AAPL")

    assert report_calls == [None, "Fix citations."]
    assert result["first_critic_review"].score == 0.5
    assert result["critic_review"].score == 0.9
    assert result["revision_count"] == 1
    assert result["quality_flag"] == "accepted"
    assert result["hitl_status"] == "ready"


@pytest.mark.asyncio
async def test_critic_loop_stops_at_three_revision_reviews(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        return {
            "ticker": ticker,
            "financials": _financials(),
            "ratios": _ratios(),
            "messages": [],
            "errors": [],
        }

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        return _sentiment()

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return _valuation()

    report_calls = 0

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        nonlocal report_calls
        report_calls += 1
        return _report().model_copy(update={"executive_summary": f"draft {report_calls}"})

    async def fake_run_report_critic(**kwargs: object) -> CriticReview:
        return CriticReview(score=0.4, verdict="revise", revision_instructions="Try again.")

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)
    monkeypatch.setattr(analyst_team_graph, "run_report_critic", fake_run_report_critic)

    result = await analyst_team_graph.run_team_analysis("AAPL")

    assert report_calls == 3
    assert result["revision_count"] == 3
    assert result["quality_flag"] == "max_revisions_reached"
    assert result["hitl_status"] == "ready"


@pytest.mark.asyncio
async def test_initial_report_writer_failure_propagates_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        return {
            "ticker": ticker,
            "financials": _financials(),
            "ratios": _ratios(),
            "messages": [],
            "errors": [],
        }

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        return _sentiment()

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return _valuation()

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        raise ValueError("structured output failed")

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)

    with pytest.raises(ValueError, match="structured output failed"):
        await analyst_team_graph.run_team_analysis("AAPL")


@pytest.mark.asyncio
async def test_critic_failure_routes_to_hitl_with_quality_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_supervisor_analysis(
        ticker: str, *, thread_id: str | None = None, config: object = None
    ) -> dict[str, object]:
        return {
            "ticker": ticker,
            "financials": _financials(),
            "ratios": _ratios(),
            "messages": [],
            "errors": [],
        }

    async def fake_run_news_sentiment(ticker: str) -> NewsSentimentResult:
        return _sentiment()

    async def fake_run_valuation(ticker: str) -> ValuationResult:
        return _valuation()

    async def fake_run_report_writer(**kwargs: object) -> AnalystReport:
        return _report()

    async def fake_run_report_critic(**kwargs: object) -> CriticReview:
        raise TimeoutError("critic unavailable")

    monkeypatch.setattr(analyst_team_graph, "run_supervisor_analysis", fake_run_supervisor_analysis)
    monkeypatch.setattr(analyst_team_graph, "run_news_sentiment", fake_run_news_sentiment)
    monkeypatch.setattr(analyst_team_graph, "run_valuation", fake_run_valuation)
    monkeypatch.setattr(analyst_team_graph, "run_report_writer", fake_run_report_writer)
    monkeypatch.setattr(analyst_team_graph, "run_report_critic", fake_run_report_critic)

    result = await analyst_team_graph.run_team_analysis("AAPL")

    assert result["hitl_status"] == "ready"
    assert result["quality_flag"] == "critic_failed"
    assert result["critic_review"] == CriticReview(
        score=0.0, verdict="accept", revision_instructions="Critic failed: critic unavailable"
    )
