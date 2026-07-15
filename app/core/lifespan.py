from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agents.analyst_team_graph import init_analyst_team_graph
from app.agents.supervisor_graph import init_supervisor_graph
from app.config import get_settings
from app.db import close_pool, open_pool
from app.services.xbrl_cache import setup as setup_xbrl_cache


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application-startup concern: opens the Postgres pool, builds and migrates the
    checkpointer, and injects it into both the 2-agent supervisor and the 5-agent analyst
    team once -- fails app startup immediately if Postgres is unreachable, rather than
    surfacing as a confusing error on whichever request happens to arrive first. One pool
    serves both compiled graphs; no second connection is opened."""
    pool = await open_pool(get_settings().postgres_url)
    try:
        # psycopg's `kwargs=` dict (set in app.db.open_pool) is untyped, so the pool's row
        # type can't be inferred as dict_row's dict[str, Any] statically -- it is dict_row
        # at runtime.
        checkpointer = AsyncPostgresSaver(conn=pool)  # type: ignore[arg-type]
        await checkpointer.setup()
        await setup_xbrl_cache(pool)
        init_supervisor_graph(checkpointer)
        init_analyst_team_graph(checkpointer)
        yield
    finally:
        await close_pool(pool)
