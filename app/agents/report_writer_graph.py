from __future__ import annotations

from typing import TypedDict, cast

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr

from app.config import get_settings
from app.models import (
    AnalystReport,
    FinancialStatements,
    FundamentalRatios,
    INVESTMENT_DISCLAIMER,
    NewsSentimentResult,
    ValuationResult,
)

_REPORT_ATTEMPTS = 2


class ReportWriterState(TypedDict):
    ticker: str
    financials: FinancialStatements | None
    ratios: FundamentalRatios | None
    sentiment: NewsSentimentResult | None
    valuation: ValuationResult | None
    previous_report: AnalystReport | None
    revision_instructions: str | None
    report: AnalystReport | None


_report_llm: Runnable[str, AnalystReport] | None = None


def _get_report_llm() -> Runnable[str, AnalystReport]:
    global _report_llm
    if _report_llm is None:
        settings = get_settings()
        # deepseek_model_routing, not deepseek_model_generation -- with_structured_output
        # requires a non-thinking model (see CLAUDE.md); deepseek_model_generation is
        # configured as a thinking model (deepseek-v4-flash) and 400s on tool_choice.
        _report_llm = cast(
            "Runnable[str, AnalystReport]",
            ChatOpenAI(
                model=settings.deepseek_model_routing,
                api_key=SecretStr(settings.deepseek_api_key),
                base_url=settings.deepseek_base_url,
            ).with_structured_output(AnalystReport, method="function_calling"),
        )
    return _report_llm


def _report_prompt(state: ReportWriterState) -> str:
    prompt = (
        f"Write an analyst report for {state['ticker']} using the following data.\n\n"
        f"Financial statements: {state['financials']}\n\n"
        f"Fundamental ratios: {state['ratios']}\n\n"
        f"News sentiment: {state['sentiment']}\n\n"
        f"Valuation vs. sector: {state['valuation']}\n\n"
        "When making narrative claims, include inline source URLs from the news sentiment "
        "articles when available.\n\n"
        "Produce an executive_summary, financial_health assessment, valuation_assessment, "
        "risk_factors, and key_themes. Leave the disclaimer field empty -- it is filled in "
        "separately."
    )
    if state["previous_report"] is not None and state["revision_instructions"]:
        prompt += (
            "\n\nRevise this prior draft instead of starting from scratch.\n"
            f"Prior draft: {state['previous_report']}\n\n"
            f"Revision instructions: {state['revision_instructions']}"
        )
    return prompt


async def _write(state: ReportWriterState) -> ReportWriterState:
    prompt = _report_prompt(state)
    report = None
    for attempt in range(_REPORT_ATTEMPTS):
        try:
            report = await _get_report_llm().ainvoke(prompt)
        except Exception:
            if attempt == _REPORT_ATTEMPTS - 1:
                raise
            continue
        if report is not None:
            break
    if report is None:
        # with_structured_output can return None if the LLM's output fails to parse. This
        # is the terminal step of the pipeline -- unlike news_sentiment's neutral fallback,
        # there's no meaningful default report to substitute, so raise clearly instead of
        # a cryptic AttributeError from .model_copy() below.
        raise ValueError(
            f"Failed to generate structured analyst report for {state['ticker']} "
            "(LLM returned None or parsing failed)"
        )
    # Deterministic compliance text -- never left to the LLM to paraphrase per-run.
    report = report.model_copy(update={"disclaimer": INVESTMENT_DISCLAIMER})
    return {**state, "report": report}


def build_report_writer_graph() -> CompiledStateGraph:
    """Report-Writer Agent subgraph: all upstream agent outputs in, final AnalystReport out."""
    graph = StateGraph(ReportWriterState)
    graph.add_node("write", _write)
    graph.add_edge(START, "write")
    graph.add_edge("write", END)
    return graph.compile()


_compiled_graph = build_report_writer_graph()


async def run_report_writer(
    *,
    ticker: str,
    financials: FinancialStatements | None,
    ratios: FundamentalRatios | None,
    sentiment: NewsSentimentResult | None,
    valuation: ValuationResult | None,
    previous_report: AnalystReport | None = None,
    revision_instructions: str | None = None,
) -> AnalystReport:
    """Report-Writer Agent entry point: all upstream agent outputs in, final AnalystReport out."""
    result = await _compiled_graph.ainvoke(
        {
            "ticker": ticker,
            "financials": financials,
            "ratios": ratios,
            "sentiment": sentiment,
            "valuation": valuation,
            "previous_report": previous_report,
            "revision_instructions": revision_instructions,
            "report": None,
        }
    )
    report = result["report"]
    assert report is not None
    return report
