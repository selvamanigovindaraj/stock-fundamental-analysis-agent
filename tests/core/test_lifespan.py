from __future__ import annotations

import pytest

from app.core import lifespan as lifespan_module


class _FakePostgresSaver:
    instances: list["_FakePostgresSaver"] = []

    def __init__(self, conn: object, *, raise_on_setup: Exception | None = None) -> None:
        self.conn = conn
        self._raise_on_setup = raise_on_setup
        self.setup_called = False
        _FakePostgresSaver.instances.append(self)

    async def setup(self) -> None:
        self.setup_called = True
        if self._raise_on_setup is not None:
            raise self._raise_on_setup


@pytest.fixture(autouse=True)
def _reset_fake_instances() -> None:
    _FakePostgresSaver.instances = []


@pytest.mark.asyncio
async def test_lifespan_opens_pool_inits_graph_and_closes_pool_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pool = object()
    open_calls: list[str] = []
    close_calls: list[object] = []
    init_calls: list[object] = []
    init_team_calls: list[object] = []

    async def fake_open_pool(url: str) -> object:
        open_calls.append(url)
        return fake_pool

    async def fake_close_pool(pool: object) -> None:
        close_calls.append(pool)

    def fake_init_supervisor_graph(checkpointer: object) -> None:
        init_calls.append(checkpointer)

    def fake_init_analyst_team_graph(checkpointer: object) -> None:
        init_team_calls.append(checkpointer)

    monkeypatch.setattr(lifespan_module, "open_pool", fake_open_pool)
    monkeypatch.setattr(lifespan_module, "close_pool", fake_close_pool)
    monkeypatch.setattr(lifespan_module, "AsyncPostgresSaver", _FakePostgresSaver)
    monkeypatch.setattr(lifespan_module, "init_supervisor_graph", fake_init_supervisor_graph)
    monkeypatch.setattr(lifespan_module, "init_analyst_team_graph", fake_init_analyst_team_graph)

    async with lifespan_module.lifespan(app=object()):  # type: ignore[arg-type]
        assert open_calls  # pool opened before yield
        assert _FakePostgresSaver.instances[0].setup_called
        assert init_calls == [_FakePostgresSaver.instances[0]]
        assert init_team_calls == [_FakePostgresSaver.instances[0]]  # same checkpointer, one pool
        assert close_calls == []  # not closed until after the context exits

    assert close_calls == [fake_pool]


@pytest.mark.asyncio
async def test_lifespan_closes_pool_even_if_checkpointer_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-fast on an unreachable/broken Postgres must not leak the connection pool."""
    fake_pool = object()
    close_calls: list[object] = []

    async def fake_open_pool(url: str) -> object:
        return fake_pool

    async def fake_close_pool(pool: object) -> None:
        close_calls.append(pool)

    def failing_saver(conn: object) -> _FakePostgresSaver:
        return _FakePostgresSaver(conn, raise_on_setup=RuntimeError("Postgres unreachable"))

    monkeypatch.setattr(lifespan_module, "open_pool", fake_open_pool)
    monkeypatch.setattr(lifespan_module, "close_pool", fake_close_pool)
    monkeypatch.setattr(lifespan_module, "AsyncPostgresSaver", failing_saver)

    with pytest.raises(RuntimeError, match="Postgres unreachable"):
        async with lifespan_module.lifespan(app=object()):  # type: ignore[arg-type]
            pass

    assert close_calls == [fake_pool]
