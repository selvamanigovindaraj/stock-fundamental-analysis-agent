from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.models import FinancialStatements
from app.observability.tracer import Tracer
from app.services.financial_sources import SourceUnavailableError
from app.services.financial_sources import edgartools_source, sec_edgar_source, yfinance_source
from app.services.guardrails import sanitize_ticker

_tracer = Tracer()


class IngestionState(TypedDict):
    ticker: str
    financials: FinancialStatements | None


async def _try_source(
    state: IngestionState, *, source_name: str, next_source: str | None
) -> IngestionState:
    fetchers = {
        "yfinance": yfinance_source.fetch_financials,
        "edgartools": edgartools_source.fetch_financials,
        "sec_edgar": sec_edgar_source.fetch_financials,
    }
    ticker = state["ticker"]
    try:
        financials = await fetchers[source_name](ticker)
        return {"ticker": ticker, "financials": financials}
    except SourceUnavailableError as exc:
        if next_source:
            _tracer.log_fallback(
                ticker=ticker, from_source=source_name, to_source=next_source, reason=str(exc)
            )
        return {"ticker": ticker, "financials": None}


async def _try_yfinance(state: IngestionState) -> IngestionState:
    return await _try_source(state, source_name="yfinance", next_source="edgartools")


async def _try_edgartools(state: IngestionState) -> IngestionState:
    return await _try_source(state, source_name="edgartools", next_source="sec_edgar")


async def _try_sec_edgar(state: IngestionState) -> IngestionState:
    return await _try_source(state, source_name="sec_edgar", next_source=None)


def _route_after_yfinance(state: IngestionState) -> str:
    return END if state["financials"] is not None else "try_edgartools"


def _route_after_edgartools(state: IngestionState) -> str:
    return END if state["financials"] is not None else "try_sec_edgar"


def build_ingestion_graph() -> CompiledStateGraph:
    """Build the DataIngestionAgent subgraph: ticker in, financials out. Fallback chain
    (yfinance -> edgartools -> sec_edgar) is expressed as the graph edges themselves."""
    graph = StateGraph(IngestionState)
    graph.add_node("try_yfinance", _try_yfinance)
    graph.add_node("try_edgartools", _try_edgartools)
    graph.add_node("try_sec_edgar", _try_sec_edgar)
    graph.add_edge(START, "try_yfinance")
    graph.add_conditional_edges("try_yfinance", _route_after_yfinance)
    graph.add_conditional_edges("try_edgartools", _route_after_edgartools)
    graph.add_edge("try_sec_edgar", END)
    return graph.compile()


_compiled_graph = build_ingestion_graph()


async def run_ingestion(ticker: str) -> FinancialStatements:
    """DataIngestionAgent entry point: ticker in, financials out."""
    ticker = sanitize_ticker(ticker)
    result = await _compiled_graph.ainvoke({"ticker": ticker, "financials": None})
    financials = result["financials"]
    if financials is None:
        raise SourceUnavailableError(f"all financial data sources failed for {ticker}")
    return financials
