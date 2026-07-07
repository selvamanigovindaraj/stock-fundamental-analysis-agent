from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import lifespan as lifespan_module
from app.main import app


def test_app_starts_and_routes_are_registered(fake_lifespan_postgres: None) -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/chat" in paths
    assert "/fundamentals/{ticker}/stream" in paths
    assert "/analysis/{ticker}/stream" in paths
    assert "/report/{ticker}/stream" in paths


def test_app_startup_fails_fast_if_checkpointer_setup_fails(
    monkeypatch: pytest.MonkeyPatch, fake_lifespan_postgres: None
) -> None:
    """An unreachable/broken Postgres must fail app startup outright, not surface later as
    a confusing error on whichever request happens to arrive first (see app/core/lifespan.py
    and tests/core/test_lifespan.py for the unit-level version of this behavior)."""

    class _FailingCheckpointer:
        def __init__(self, conn: object) -> None:
            pass

        async def setup(self) -> None:
            raise RuntimeError("Postgres unreachable")

    monkeypatch.setattr(lifespan_module, "AsyncPostgresSaver", _FailingCheckpointer)

    with pytest.raises(RuntimeError, match="Postgres unreachable"), TestClient(app):
        pass
