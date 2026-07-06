from __future__ import annotations


async def get_fundamentals(ticker: str) -> dict[str, float]:
    """Fetch fundamental financial data (P/E, EPS, ROE, etc.) for a ticker."""
    raise NotImplementedError


async def get_filings(ticker: str) -> list[dict[str, str]]:
    """Fetch recent regulatory filings (10-K, 10-Q) for a ticker."""
    raise NotImplementedError
