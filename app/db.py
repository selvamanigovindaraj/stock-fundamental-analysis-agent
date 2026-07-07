from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


async def open_pool(url: str) -> AsyncConnectionPool[Any]:
    """Open and return an async connection pool using dict rows."""
    pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
        conninfo=url, open=False, kwargs={"autocommit": True, "row_factory": dict_row}
    )
    await pool.open()
    return pool


async def close_pool(pool: AsyncConnectionPool[Any]) -> None:
    """Close the connection pool gracefully."""
    await pool.close()
