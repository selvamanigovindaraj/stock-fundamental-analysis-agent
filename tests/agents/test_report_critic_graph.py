from __future__ import annotations

import pytest

from app.agents import report_critic_graph
from app.models import AnalystReport, CriticReview, FundamentalRatios


class _FakeCriticLLM:
    def __init__(self, review: CriticReview | None = None) -> None:
        self._review = review
        self.last_prompt = ""

    async def ainvoke(self, prompt: str) -> CriticReview | None:
        self.last_prompt = prompt
        return self._review


def _report() -> AnalystReport:
    return AnalystReport(
        ticker="AAPL",
        executive_summary="Revenue improved.",
        financial_health="ROE was 20%.",
        valuation_assessment="Fairly valued.",
        risk_factors=["supply risk"],
        key_themes=["growth"],
        disclaimer="ok",
    )


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
        roe=0.2,
        roa=0.1,
        asset_turnover=0.5,
        free_cash_flow=30.0,
        operating_cash_flow_ratio=1.4,
    )


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_critic_graph, "_critic_llm", None)


@pytest.mark.asyncio
async def test_run_report_critic_returns_structured_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = CriticReview(
        score=0.72,
        verdict="revise",
        revision_instructions="Correct ROE wording and cite the news URL.",
    )
    fake_llm = _FakeCriticLLM(expected)
    monkeypatch.setattr(report_critic_graph, "_critic_llm", fake_llm)

    review = await report_critic_graph.run_report_critic(
        ticker="AAPL",
        report=_report(),
        ratios=_ratios(),
        source_urls=["https://example.com/news"],
    )

    assert review == expected
    assert "numerical accuracy" in fake_llm.last_prompt
    assert "https://example.com/news" in fake_llm.last_prompt
    assert "at least 0.80" in fake_llm.last_prompt


@pytest.mark.asyncio
async def test_run_report_critic_prompt_handles_missing_ratios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = CriticReview(score=0.82, verdict="accept")
    fake_llm = _FakeCriticLLM(expected)
    monkeypatch.setattr(report_critic_graph, "_critic_llm", fake_llm)

    review = await report_critic_graph.run_report_critic(
        ticker="AAPL",
        report=_report(),
        ratios=None,
        source_urls=[],
    )

    assert review == expected
    assert "no ratios object is available" in fake_llm.last_prompt
    assert "Ratios object:" not in fake_llm.last_prompt


@pytest.mark.asyncio
async def test_run_report_critic_raises_clear_error_when_llm_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(report_critic_graph, "_critic_llm", _FakeCriticLLM(None))

    with pytest.raises(ValueError, match="AAPL"):
        await report_critic_graph.run_report_critic(
            ticker="AAPL",
            report=_report(),
            ratios=_ratios(),
            source_urls=[],
        )
