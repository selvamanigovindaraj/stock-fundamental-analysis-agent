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


class _FakeCheckpointer:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def setup(self) -> None:
        pass


@pytest.fixture
def fake_lifespan_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """`TestClient(app)` triggers the real `app.core.lifespan.lifespan` on startup --
    request this fixture in any test that constructs one, so it never opens a real
    Postgres socket. `init_supervisor_graph` itself is faked to a no-op too, since these
    HTTP-level tests exercise routing/streaming, not the supervisor graph internals
    (which have their own dedicated, real-checkpointer-free tests)."""

    async def fake_open_pool(url: str) -> object:
        return object()

    async def fake_close_pool(pool: object) -> None:
        pass

    def fake_init_supervisor_graph(checkpointer: object) -> None:
        pass

    monkeypatch.setattr(lifespan_module, "open_pool", fake_open_pool)
    monkeypatch.setattr(lifespan_module, "close_pool", fake_close_pool)
    monkeypatch.setattr(lifespan_module, "AsyncPostgresSaver", _FakeCheckpointer)
    monkeypatch.setattr(lifespan_module, "init_supervisor_graph", fake_init_supervisor_graph)
