from __future__ import annotations

import logging
import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents import supervisor_graph
from app.models import BalanceSheet, CashFlowStatement, FinancialStatements, IncomeStatement
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


class _FakeRoutingLLM:
    """Fake structured-output-bound runnable: `ainvoke` returns a RoutingDecision directly,
    matching what `ChatOpenAI(...).with_structured_output(RoutingDecision, ...)` returns."""

    def __init__(
        self, decisions: list[object] | None = None, *, raises: Exception | None = None
    ) -> None:
        self._decisions = decisions or []
        self._raises = raises
        self.calls: list[str] = []

    async def ainvoke(self, prompt: str) -> object:
        self.calls.append(prompt)
        if self._raises is not None:
            raise self._raises
        return self._decisions[len(self.calls) - 1]


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(supervisor_graph, "_routing_llm", None)


@pytest.fixture(autouse=True)
def _use_in_memory_checkpointer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production wires a real Postgres checkpointer into `init_supervisor_graph` from
    `app.core.lifespan` at app startup -- never exercised for real in unit tests. Call the
    real `init_supervisor_graph` with an `InMemorySaver` instead, so every test still runs
    through the actual function `run_supervisor_analysis` depends on, without ever opening
    a real socket."""
    supervisor_graph.init_supervisor_graph(InMemorySaver())
    yield
    monkeypatch.setattr(supervisor_graph, "_compiled_graph", None)


@pytest.mark.asyncio
async def test_run_supervisor_analysis_before_init_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_supervisor_graph() must be called (from app.core.lifespan at startup) before
    run_supervisor_analysis() can work -- a clear assertion, not a confusing AttributeError
    deep inside graph internals, if someone calls it too early."""
    monkeypatch.setattr(supervisor_graph, "_compiled_graph", None)

    with pytest.raises(AssertionError, match="init_supervisor_graph"):
        await supervisor_graph.run_supervisor_analysis("AAPL")


@pytest.mark.asyncio
async def test_full_sequence_ingestion_then_ratio_analysis_then_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _statements()

    async def fake_run_ingestion(ticker: str) -> FinancialStatements:
        return statements

    monkeypatch.setattr(supervisor_graph, "run_ingestion", fake_run_ingestion)

    routing_llm = _FakeRoutingLLM(
        decisions=[
            supervisor_graph.RoutingDecision(
                next_agent="data_ingestion", task="fetch financials", reasoning="none yet"
            ),
            supervisor_graph.RoutingDecision(
                next_agent="ratio_analysis", task="compute ratios", reasoning="financials ready"
            ),
            supervisor_graph.RoutingDecision(
                next_agent="FINISH", task="done", reasoning="ratios ready"
            ),
        ]
    )
    monkeypatch.setattr(supervisor_graph, "_routing_llm", routing_llm)

    result = await supervisor_graph.run_supervisor_analysis("AAPL")

    assert result["financials"] == statements
    assert result["ratios"] is not None
    assert routing_llm.calls  # supervisor was actually consulted


@pytest.mark.asyncio
async def test_ingestion_failure_raises_source_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_ingestion(ticker: str) -> FinancialStatements:
        raise SourceUnavailableError("all sources failed for BADTICKER")

    monkeypatch.setattr(supervisor_graph, "run_ingestion", fake_run_ingestion)

    ratio_analysis_calls = 0

    async def fake_run_ratio_analysis(financials: FinancialStatements) -> object:
        nonlocal ratio_analysis_calls
        ratio_analysis_calls += 1
        raise AssertionError("ratio_analysis should never be invoked")

    monkeypatch.setattr(supervisor_graph, "run_ratio_analysis", fake_run_ratio_analysis)

    routing_llm = _FakeRoutingLLM(
        decisions=[
            supervisor_graph.RoutingDecision(
                next_agent="data_ingestion", task="fetch financials", reasoning="none yet"
            ),
            supervisor_graph.RoutingDecision(next_agent="FINISH", task="done", reasoning="failed"),
        ]
    )
    monkeypatch.setattr(supervisor_graph, "_routing_llm", routing_llm)

    with pytest.raises(SourceUnavailableError):
        await supervisor_graph.run_supervisor_analysis("BADTICKER")

    assert ratio_analysis_calls == 0


@pytest.mark.asyncio
async def test_routing_llm_failure_falls_back_to_deterministic_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _statements()

    async def fake_run_ingestion(ticker: str) -> FinancialStatements:
        return statements

    monkeypatch.setattr(supervisor_graph, "run_ingestion", fake_run_ingestion)
    monkeypatch.setattr(
        supervisor_graph, "_routing_llm", _FakeRoutingLLM(raises=RuntimeError("DeepSeek down"))
    )

    result = await supervisor_graph.run_supervisor_analysis("AAPL")

    assert result["financials"] == statements
    assert result["ratios"] is not None
    assert any("fallback" in m.lower() for m in result["messages"])


@pytest.mark.asyncio
async def test_llm_reroutes_to_already_satisfied_agent_is_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The LLM insisting on re-running data_ingestion after financials is already populated
    must be overridden by the supervisor's hard invariant, not obeyed -- this also prevents
    infinite Command(goto=...) loops."""
    statements = _statements()
    ingestion_calls = 0

    async def fake_run_ingestion(ticker: str) -> FinancialStatements:
        nonlocal ingestion_calls
        ingestion_calls += 1
        return statements

    monkeypatch.setattr(supervisor_graph, "run_ingestion", fake_run_ingestion)

    routing_llm = _FakeRoutingLLM(
        decisions=[
            supervisor_graph.RoutingDecision(
                next_agent="data_ingestion", task="fetch financials", reasoning="none yet"
            ),
            # Wrong: financials is already set, but the LLM says data_ingestion again.
            supervisor_graph.RoutingDecision(
                next_agent="data_ingestion", task="fetch again", reasoning="oops"
            ),
            supervisor_graph.RoutingDecision(
                next_agent="FINISH", task="done", reasoning="ratios ready"
            ),
        ]
    )
    monkeypatch.setattr(supervisor_graph, "_routing_llm", routing_llm)

    result = await supervisor_graph.run_supervisor_analysis("AAPL")

    assert ingestion_calls == 1
    assert result["ratios"] is not None
    assert any("override" in m.lower() or "correct" in m.lower() for m in result["messages"])


@pytest.mark.asyncio
async def test_llm_reroutes_to_ratio_analysis_before_financials_is_corrected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The LLM jumping straight to ratio_analysis before financials exists must be corrected
    to data_ingestion, not obeyed -- ratio_analysis would otherwise be invoked with
    financials=None and crash."""
    statements = _statements()

    async def fake_run_ingestion(ticker: str) -> FinancialStatements:
        return statements

    monkeypatch.setattr(supervisor_graph, "run_ingestion", fake_run_ingestion)

    routing_llm = _FakeRoutingLLM(
        decisions=[
            supervisor_graph.RoutingDecision(
                next_agent="ratio_analysis", task="compute ratios", reasoning="premature"
            ),
            supervisor_graph.RoutingDecision(
                next_agent="ratio_analysis", task="compute ratios", reasoning="financials ready"
            ),
            supervisor_graph.RoutingDecision(
                next_agent="FINISH", task="done", reasoning="ratios ready"
            ),
        ]
    )
    monkeypatch.setattr(supervisor_graph, "_routing_llm", routing_llm)

    result = await supervisor_graph.run_supervisor_analysis("AAPL")

    assert result["financials"] == statements
    assert result["ratios"] is not None
    assert any("correct" in m.lower() for m in result["messages"])


@pytest.mark.asyncio
async def test_checkpoint_resume_persists_financials_across_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _statements()

    async def fake_run_ingestion(ticker: str) -> FinancialStatements:
        return statements

    monkeypatch.setattr(supervisor_graph, "run_ingestion", fake_run_ingestion)
    monkeypatch.setattr(
        supervisor_graph,
        "_routing_llm",
        _FakeRoutingLLM(
            decisions=[
                supervisor_graph.RoutingDecision(
                    next_agent="data_ingestion", task="fetch financials", reasoning="none yet"
                ),
            ]
        ),
    )

    checkpointer = InMemorySaver()
    graph = supervisor_graph.build_supervisor_graph(checkpointer)
    config = {"configurable": {"thread_id": "AAPL"}}

    # Simulate a process crash right after the data_ingestion checkpoint is saved, before the
    # supervisor gets to make its next routing decision.
    first_run = await graph.ainvoke(
        {
            "ticker": "AAPL",
            "financials": None,
            "ratios": None,
            "messages": [],
            "errors": [],
            "visited": [],
        },
        config,
        interrupt_after=["data_ingestion"],
    )
    assert first_run["financials"] == statements
    assert first_run["ratios"] is None  # crash-simulated: stopped before ratio_analysis

    monkeypatch.setattr(
        supervisor_graph,
        "_routing_llm",
        _FakeRoutingLLM(
            decisions=[
                supervisor_graph.RoutingDecision(
                    next_agent="ratio_analysis", task="compute ratios", reasoning="resumed"
                ),
                supervisor_graph.RoutingDecision(
                    next_agent="FINISH", task="done", reasoning="ratios ready"
                ),
            ]
        ),
    )

    state = await graph.aget_state(config)
    assert state.values["financials"] == statements  # persisted checkpoint, not re-fetched

    resumed = await graph.ainvoke(None, config)
    assert resumed["ratios"] is not None


class _FanOutState(TypedDict):
    messages: Annotated[list[str], operator.add]


async def _append_a(state: _FanOutState) -> _FanOutState:
    return {"messages": ["a"]}


async def _append_b(state: _FanOutState) -> _FanOutState:
    return {"messages": ["b"]}


def _fan_out(state: _FanOutState) -> list[Send]:
    return [Send("append_a", state), Send("append_b", state)]


@pytest.mark.asyncio
async def test_operator_add_reducer_survives_genuine_concurrent_writes() -> None:
    """Validates the operator.add reducer primitive itself under real concurrent writes to
    the same state field -- not the supervisor_graph's own execution, which is sequential.
    Proves the mechanism the goal asks for (InvalidUpdateError avoidance) honestly."""
    graph = StateGraph(_FanOutState)
    graph.add_node("append_a", _append_a)
    graph.add_node("append_b", _append_b)
    graph.add_conditional_edges(START, _fan_out, ["append_a", "append_b"])
    graph.add_edge("append_a", END)
    graph.add_edge("append_b", END)
    compiled = graph.compile()

    result = await compiled.ainvoke({"messages": []})

    assert sorted(result["messages"]) == ["a", "b"]


def test_strict_msgpack_allowlist_is_derived_from_supervisor_state_schema() -> None:
    """LANGGRAPH_STRICT_MSGPACK=true (set in tests/conftest.py) makes
    StateGraph.compile() walk SupervisorState's own field types and call
    checkpointer.with_allowlist(...) automatically -- this is the framework's own
    supported mechanism (see the GHSA-g48c-2wqr-h844 advisory and
    langgraph/graph/state.py's compile()), not a hand-maintained allowlist. Confirms our
    checkpointed Pydantic models (including ones nested inside FinancialStatements) are
    picked up without us listing them anywhere."""
    graph = supervisor_graph.build_supervisor_graph(InMemorySaver())

    allowlist = graph.checkpointer.serde._allowed_msgpack_modules

    assert ("app.models", "FinancialStatements") in allowlist
    assert ("app.models", "FundamentalRatios") in allowlist


def test_checkpointed_financials_and_ratios_round_trip_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Confirms the strict-mode-derived allowlist actually lets our checkpointed state
    round-trip through the checkpointer's own serde without LangGraph's "unregistered
    type"/"blocked deserialization" log lines -- not just that the allowlist set contains
    the right tuples."""
    statements = _statements()
    ratios = RatioEngine.compute(statements)
    graph = supervisor_graph.build_supervisor_graph(InMemorySaver())
    serde = graph.checkpointer.serde

    with caplog.at_level(logging.WARNING, logger="langgraph.checkpoint.serde.jsonplus"):
        for obj in (statements, ratios):
            type_, payload = serde.dumps_typed(obj)
            assert serde.loads_typed((type_, payload)) == obj

    assert "unregistered type" not in caplog.text.lower()
    assert "blocked deserialization" not in caplog.text.lower()
