from __future__ import annotations

import os

import pytest

# Must be set before any `langgraph` import in the process -- `STRICT_MSGPACK_ENABLED` is
# read once from this env var at `langgraph.checkpoint.serde._msgpack` import time, and
# `langgraph.graph.state.StateGraph.compile()` only derives/applies a checkpoint serde
# allowlist from the graph's state schema when it's true. Setting it here (in the root
# conftest, loaded before any test module) makes the test suite exercise the same strict
# msgpack posture as production (see .env.example / CLAUDE.md).
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from app.core import lifespan as lifespan_module  # noqa: E402
from app.models import (  # noqa: E402
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)


def make_financial_statements(ticker: str = "AAPL") -> FinancialStatements:
    """Shared fixture builder -- used by test_supervisor_graph.py, test_analyst_team_graph.py,
    and test_streaming.py, which all previously carried their own copy-pasted version."""
    return FinancialStatements(
        ticker=ticker,
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


class _FakeCheckpointer:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def setup(self) -> None:
        pass


@pytest.fixture
def fake_lifespan_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """`TestClient(app)` triggers the real `app.core.lifespan.lifespan` on startup --
    request this fixture in any test that constructs one, so it never opens a real
    Postgres socket. `init_supervisor_graph`/`init_analyst_team_graph` themselves are
    faked to no-ops too, since these HTTP-level tests exercise routing/streaming, not the
    graph internals (which have their own dedicated, real-checkpointer-free tests)."""

    async def fake_open_pool(url: str) -> object:
        return object()

    async def fake_close_pool(pool: object) -> None:
        pass

    async def fake_setup_xbrl_cache(pool: object) -> None:
        pass

    def fake_init_supervisor_graph(checkpointer: object) -> None:
        pass

    def fake_init_analyst_team_graph(checkpointer: object) -> None:
        pass

    monkeypatch.setattr(lifespan_module, "open_pool", fake_open_pool)
    monkeypatch.setattr(lifespan_module, "close_pool", fake_close_pool)
    monkeypatch.setattr(lifespan_module, "setup_xbrl_cache", fake_setup_xbrl_cache)
    monkeypatch.setattr(lifespan_module, "AsyncPostgresSaver", _FakeCheckpointer)
    monkeypatch.setattr(lifespan_module, "init_supervisor_graph", fake_init_supervisor_graph)
    monkeypatch.setattr(lifespan_module, "init_analyst_team_graph", fake_init_analyst_team_graph)
