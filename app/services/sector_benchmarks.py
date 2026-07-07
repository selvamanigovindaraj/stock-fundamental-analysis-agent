from __future__ import annotations

import asyncio

import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models import SectorBenchmark

# Curated ~5-peer basket per sector, used only to know *which* tickers to fetch live data
# for -- the benchmark numbers themselves always come from a live yfinance call, never a
# hardcoded value. Keys must match yfinance's own sector taxonomy strings exactly
# (verified live: "Technology", "Healthcare", "Energy", "Financial Services", etc.).
_SECTOR_PEERS: dict[str, list[str]] = {
    "Technology": ["MSFT", "GOOGL", "META", "NVDA", "ORCL"],
    "Healthcare": ["JNJ", "PFE", "UNH", "MRK", "ABBV"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
    "Communication Services": ["META", "GOOGL", "NFLX", "DIS", "CMCSA"],
    "Industrials": ["HON", "UNP", "CAT", "GE", "BA"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST"],
}


@retry(
    stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.1, min=0.1, max=1), reraise=True
)
async def fetch_market_ratios(ticker: str) -> tuple[float | None, float | None, float | None]:
    """Live trailing P/E, P/B, and ROE for a single ticker via yfinance."""
    info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
    if not info:
        # Invalid/delisted tickers or a transient yfinance API failure can come back as
        # None or an empty dict rather than raising.
        return None, None, None
    return info.get("trailingPE"), info.get("priceToBook"), info.get("returnOnEquity")


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


async def fetch_sector_benchmark(ticker: str) -> SectorBenchmark:
    """Live sector-peer median P/E, P/B, and ROE for ticker's sector. Never raises --
    degrades to all-None medians (with the reason recorded in `errors`) if the sector is
    unknown or every peer fetch fails."""
    try:
        info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
        sector = info.get("sector") or "unknown"
    except Exception as exc:
        return SectorBenchmark(
            sector="unknown",
            median_pe=None,
            median_pb=None,
            median_roe=None,
            peers_used=[],
            errors=[f"failed to resolve sector for {ticker}: {exc}"],
        )

    peers = _SECTOR_PEERS.get(sector)
    if not peers:
        return SectorBenchmark(
            sector=sector,
            median_pe=None,
            median_pb=None,
            median_roe=None,
            peers_used=[],
            errors=[f"no peer basket configured for sector {sector!r}"],
        )

    results = await asyncio.gather(
        *(fetch_market_ratios(peer) for peer in peers), return_exceptions=True
    )

    errors: list[str] = []
    peers_used: list[str] = []
    pes: list[float] = []
    pbs: list[float] = []
    roes: list[float] = []
    for peer, result in zip(peers, results, strict=True):
        if isinstance(result, BaseException):
            errors.append(f"peer {peer} fetch failed: {result}")
            continue
        pe, pb, roe = result
        peers_used.append(peer)
        if pe is not None:
            pes.append(pe)
        if pb is not None:
            pbs.append(pb)
        if roe is not None:
            roes.append(roe)

    return SectorBenchmark(
        sector=sector,
        median_pe=_median(pes),
        median_pb=_median(pbs),
        median_roe=_median(roes),
        peers_used=peers_used,
        errors=errors,
    )
