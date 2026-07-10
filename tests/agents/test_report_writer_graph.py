from __future__ import annotations

import pytest

from app.agents import report_writer_graph
from app.models import AnalystReport, ArticleSentiment, NewsSentimentResult, ValuationResult


class _FakeReportLLM:
    def __init__(self, report: AnalystReport) -> None:
        self._report = report
        self.invoke_count = 0
        self.last_prompt = ""

    async def ainvoke(self, prompt: str) -> AnalystReport:
        self.invoke_count += 1
        self.last_prompt = prompt
        return self._report


def _sentiment() -> NewsSentimentResult:
    return NewsSentimentResult(
        ticker="AAPL",
        sentiment="positive",
        score=0.7,
        key_themes=["strong earnings"],
        articles=[ArticleSentiment(title="t", url="u", sentiment="positive", score=0.7)],
    )


def _valuation() -> ValuationResult:
    return ValuationResult(
        ticker="AAPL",
        valuation_verdict="fairly_valued",
        vs_sector={"pe": 1.0, "pb": 1.0, "roe": 1.0},
        risk_flags=[],
    )


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_writer_graph, "_report_llm", None)


@pytest.mark.asyncio
async def test_run_report_writer_always_overrides_disclaimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm_report = AnalystReport(
        ticker="AAPL",
        executive_summary="Strong quarter.",
        financial_health="Healthy margins.",
        valuation_assessment="Fairly valued.",
        risk_factors=["supply chain"],
        key_themes=["strong earnings"],
        disclaimer="whatever the LLM made up",
    )
    fake_llm = _FakeReportLLM(llm_report)
    monkeypatch.setattr(report_writer_graph, "_report_llm", fake_llm)

    result = await report_writer_graph.run_report_writer(
        ticker="AAPL", financials=None, ratios=None, sentiment=_sentiment(), valuation=_valuation()
    )

    assert result.disclaimer == report_writer_graph._DISCLAIMER
    assert result.disclaimer != "whatever the LLM made up"
    assert result.executive_summary == "Strong quarter."
    assert fake_llm.invoke_count == 1
    assert "strong earnings" in fake_llm.last_prompt


@pytest.mark.asyncio
async def test_run_report_writer_raises_a_clear_error_when_llm_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """with_structured_output can return None if the LLM's output fails to parse -- must
    raise a clear error instead of an AttributeError from calling .model_copy() on None
    (caught in PR review)."""

    class _NoneReturningLLM:
        async def ainvoke(self, prompt: str) -> None:
            return None

    monkeypatch.setattr(report_writer_graph, "_report_llm", _NoneReturningLLM())

    with pytest.raises(ValueError, match="AAPL"):
        await report_writer_graph.run_report_writer(
            ticker="AAPL",
            financials=None,
            ratios=None,
            sentiment=_sentiment(),
            valuation=_valuation(),
        )
