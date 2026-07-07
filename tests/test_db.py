from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import db


@pytest.mark.asyncio
async def test_open_pool_constructs_with_dict_row_and_opens_it() -> None:
    fake_pool = MagicMock()
    fake_pool.open = AsyncMock()

    with patch.object(db, "AsyncConnectionPool", return_value=fake_pool) as fake_cls:
        result = await db.open_pool("postgresql://example")

    fake_cls.assert_called_once()
    _, kwargs = fake_cls.call_args
    assert kwargs["conninfo"] == "postgresql://example"
    assert kwargs["open"] is False
    assert kwargs["kwargs"]["autocommit"] is True
    fake_pool.open.assert_awaited_once()
    assert result is fake_pool


@pytest.mark.asyncio
async def test_close_pool_closes_it() -> None:
    fake_pool = MagicMock()
    fake_pool.close = AsyncMock()

    await db.close_pool(fake_pool)

    fake_pool.close.assert_awaited_once()
