from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict, cast

from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from app.agents.ingestion_graph import run_ingestion
from app.agents.ratio_analysis_graph import run_ratio_analysis
from app.config import get_settings
from app.models import FinancialStatements, FundamentalRatios
from app.services.financial_sources import SourceUnavailableError

_WorkerName = Literal["data_ingestion", "ratio_analysis", "FINISH"]


class RoutingDecision(BaseModel):
    """Supervisor's structured-output routing decision -- graph-internal plumbing, not an
    I/O-facing model, so it lives here rather than in app/models.py."""

    next_agent: _WorkerName
    task: str
    reasoning: str


class SupervisorState(TypedDict):
    ticker: str
    financials: FinancialStatements | None
    ratios: FundamentalRatios | None
    messages: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    # Which workers have already completed a run (success or failure) -- distinct from
    # `messages` (a human-readable log), this is the actual control-flow signal so routing
    # never has to parse log text to know what's already happened.
    visited: Annotated[list[str], operator.add]


_routing_llm: Runnable[str, RoutingDecision] | None = None


def _get_routing_llm() -> Runnable[str, RoutingDecision]:
    global _routing_llm
    if _routing_llm is None:
        settings = get_settings()
        _routing_llm = cast(
            "Runnable[str, RoutingDecision]",
            ChatOpenAI(
                model=settings.deepseek_model_routing,
                api_key=SecretStr(settings.deepseek_api_key),
                base_url=settings.deepseek_base_url,
            ).with_structured_output(RoutingDecision, method="function_calling"),
        )
    return _routing_llm


def _has_run(state: SupervisorState, agent: str) -> bool:
    return agent in state["visited"]


def _deterministic_next(state: SupervisorState) -> _WorkerName:
    """The one true routing order for this fixed 2-worker pipeline: ingestion, then ratios,
    then finish. Used both as the fallback when the routing LLM call fails, and to validate
    the LLM's actual decision against the "never re-invoke a worker whose output is already
    present" invariant."""
    if state["financials"] is None:
        return "FINISH" if _has_run(state, "data_ingestion") else "data_ingestion"
    if state["ratios"] is None:
        return "ratio_analysis"
    return "FINISH"


def _routing_prompt(state: SupervisorState) -> str:
    return (
        f"You are supervising a two-worker stock analysis pipeline for ticker {state['ticker']}.\n"
        f"financials populated: {state['financials'] is not None}\n"
        f"ratios populated: {state['ratios'] is not None}\n"
        f"errors so far: {state['errors']}\n"
        "Decide the next step: 'data_ingestion' (fetch financial statements), "
        "'ratio_analysis' (compute ratios from financials), or 'FINISH'."
    )


def _apply_invariant(
    next_agent: _WorkerName, state: SupervisorState
) -> tuple[_WorkerName, list[str]]:
    """Never let the LLM's decision re-invoke a worker whose output is already present, or
    invoke ratio_analysis before financials exists -- corrects the decision to the
    deterministic next step instead, logging the correction."""
    if next_agent == "data_ingestion" and state["financials"] is not None:
        corrected = _deterministic_next(state)
        return corrected, [
            f"supervisor: override LLM decision to re-run data_ingestion -> {corrected}"
        ]
    if next_agent == "ratio_analysis" and state["financials"] is None:
        corrected = _deterministic_next(state)
        return corrected, [
            f"supervisor: correct premature ratio_analysis (no financials yet) -> {corrected}"
        ]
    if next_agent == "ratio_analysis" and state["ratios"] is not None:
        return "FINISH", ["supervisor: override LLM decision to re-run ratio_analysis -> FINISH"]
    return next_agent, []


async def _supervisor(state: SupervisorState) -> Command:
    try:
        decision = await _get_routing_llm().ainvoke(_routing_prompt(state))
        next_agent, messages = _apply_invariant(decision.next_agent, state)
    except Exception as exc:  # noqa: BLE001 - any LLM/client failure falls back identically
        next_agent = _deterministic_next(state)
        messages = [f"supervisor: routing LLM call failed ({exc}), fallback to {next_agent}"]

    return Command(
        update={"messages": messages}, goto=END if next_agent == "FINISH" else next_agent
    )


async def _data_ingestion(state: SupervisorState) -> SupervisorState:
    try:
        financials = await run_ingestion(state["ticker"])
        return {
            **state,
            "financials": financials,
            "messages": ["data_ingestion: fetched financials"],
            "visited": ["data_ingestion"],
        }
    except SourceUnavailableError as exc:
        return {
            **state,
            "errors": [f"data_ingestion: {exc}"],
            "messages": [f"data_ingestion: failed - {exc}"],
            "visited": ["data_ingestion"],
        }


async def _ratio_analysis(state: SupervisorState) -> SupervisorState:
    financials = state["financials"]
    if financials is None:
        raise ValueError("ratio_analysis invoked before financials were populated")
    ratios = await run_ratio_analysis(financials)
    return {
        **state,
        "ratios": ratios,
        "messages": ["ratio_analysis: computed ratios"],
        "visited": ["ratio_analysis"],
    }


def build_supervisor_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Supervisor pattern: a Command(goto=...)-driven supervisor node dispatches to two
    compiled-subgraph workers (data_ingestion, ratio_analysis), each returning control to the
    supervisor for the next routing decision, until the supervisor emits FINISH."""
    graph = StateGraph(SupervisorState)
    graph.add_node(
        "supervisor", _supervisor, destinations=("data_ingestion", "ratio_analysis", END)
    )
    graph.add_node("data_ingestion", _data_ingestion)
    graph.add_node("ratio_analysis", _ratio_analysis)
    graph.add_edge(START, "supervisor")
    graph.add_edge("data_ingestion", "supervisor")
    graph.add_edge("ratio_analysis", "supervisor")
    return graph.compile(checkpointer=checkpointer)


_compiled_graph: CompiledStateGraph | None = None


def init_supervisor_graph(checkpointer: BaseCheckpointSaver) -> None:
    """Compile and register the supervisor graph; must be called once during app startup
    (see app.core.lifespan) before run_supervisor_analysis() can work. This module owns no
    Postgres/connection-lifecycle concerns of its own -- the checkpointer is built and its
    lifetime managed entirely by the caller (app.core.lifespan + app.db), and simply
    injected here."""
    global _compiled_graph
    _compiled_graph = build_supervisor_graph(checkpointer)


async def run_supervisor_analysis(
    ticker: str, *, thread_id: str | None = None, config: RunnableConfig | None = None
) -> SupervisorState:
    """Supervisor entry point: ticker in, final SupervisorState out. Raises
    SourceUnavailableError if data ingestion never produced financials (mirroring
    run_ingestion's own contract) -- callers never see a silently half-populated result.

    `config` lets a caller (e.g. the outer analyst-team graph, reusing this whole
    supervisor as a black-box branch) pass its own RunnableConfig through -- thread_id is
    still overridden to the caller-supplied value (so this subgraph's checkpoints land in
    a distinct thread from the caller's own), but callbacks/run metadata are preserved, so
    LangSmith traces nest this run under the caller's instead of appearing top-level."""
    assert _compiled_graph is not None, (
        "init_supervisor_graph() must be called before run_supervisor_analysis()"
    )
    merged_config: RunnableConfig = {
        **(config or {}),
        "configurable": {
            **(config or {}).get("configurable", {}),
            "thread_id": thread_id or ticker,
        },
    }
    config = merged_config
    initial_state: SupervisorState = {
        "ticker": ticker,
        "financials": None,
        "ratios": None,
        "messages": [],
        "errors": [],
        "visited": [],
    }
    result = cast(SupervisorState, await _compiled_graph.ainvoke(initial_state, config))
    if result["ratios"] is None:
        raise SourceUnavailableError(f"{ticker}: " + "; ".join(result["errors"]))
    return result
