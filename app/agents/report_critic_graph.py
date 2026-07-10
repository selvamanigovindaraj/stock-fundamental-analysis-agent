from __future__ import annotations

from typing import cast

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import get_settings
from app.models import AnalystReport, CRITIC_QUALITY_THRESHOLD, CriticReview, FundamentalRatios
from app.services.guardrails import sanitize_ticker


_critic_llm: Runnable[str, CriticReview] | None = None


def _get_critic_llm() -> Runnable[str, CriticReview]:
    global _critic_llm
    if _critic_llm is None:
        settings = get_settings()
        _critic_llm = cast(
            "Runnable[str, CriticReview]",
            ChatOpenAI(
                model=settings.deepseek_model_routing,
                api_key=SecretStr(settings.deepseek_api_key),
                base_url=settings.deepseek_base_url,
            ).with_structured_output(CriticReview, method="function_calling"),
        )
    return _critic_llm


def _critic_prompt(
    *,
    ticker: str,
    report: AnalystReport,
    ratios: FundamentalRatios | None,
    source_urls: list[str],
) -> str:
    ratios_rubric = (
        "1. numerical accuracy: every figure in the report must match the ratios object.\n"
        if ratios is not None
        else "1. numerical accuracy: verify internal consistency of figures "
        "(no ratios object is available for comparison).\n"
    )
    ratios_data = f"Ratios object: {ratios}\n\n" if ratios is not None else ""
    return (
        f"Review this analyst report draft for {ticker}.\n\n"
        "Rubric, score 0.0 to 1.0:\n"
        f"{ratios_rubric}"
        "2. completeness: executive_summary, financial_health, valuation_assessment, "
        "risk_factors, key_themes, and disclaimer must be present.\n"
        "3. grounding: narrative claims should cite available EDGAR filing or news source "
        "URLs. If filing URLs are unavailable in the inputs, penalize uncited filing claims.\n"
        "4. disclaimer: required investment-advice disclaimer must be present.\n\n"
        f"Return accept only when score is at least {CRITIC_QUALITY_THRESHOLD:.2f}. "
        "Otherwise return revise with specific revision_instructions.\n\n"
        f"{ratios_data}"
        f"Available source URLs: {source_urls}\n\n"
        f"Report draft: {report}"
    )


async def run_report_critic(
    *,
    ticker: str,
    report: AnalystReport,
    ratios: FundamentalRatios | None,
    source_urls: list[str],
) -> CriticReview:
    ticker = sanitize_ticker(ticker)
    review = await _get_critic_llm().ainvoke(
        _critic_prompt(ticker=ticker, report=report, ratios=ratios, source_urls=source_urls)
    )
    if review is None:
        raise ValueError(
            f"Failed to generate structured critic review for {ticker} "
            "(LLM returned None or parsing failed)"
        )
    return review
