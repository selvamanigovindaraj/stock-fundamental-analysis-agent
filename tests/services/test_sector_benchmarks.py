from __future__ import annotations

import pytest

from app.services import sector_benchmarks


def _fake_ticker(info: dict[str, object]) -> object:
    class FakeTicker:
        pass

    FakeTicker.info = info  # type: ignore[attr-defined]
    return FakeTicker()


@pytest.mark.asyncio
async def test_fetch_market_ratios_returns_pe_pb_roe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sector_benchmarks.yf,
        "Ticker",
        lambda ticker: _fake_ticker(
            {"trailingPE": 30.0, "priceToBook": 40.0, "returnOnEquity": 1.4}
        ),
    )

    pe, pb, roe = await sector_benchmarks.fetch_market_ratios("AAPL")

    assert (pe, pb, roe) == (30.0, 40.0, 1.4)


@pytest.mark.asyncio
async def test_fetch_market_ratios_tolerates_none_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """yfinance can return `info=None` (or an empty dict) for invalid/delisted tickers or
    during a temporary API failure -- calling `.get(...)` on that would otherwise raise
    AttributeError."""
    monkeypatch.setattr(sector_benchmarks.yf, "Ticker", lambda ticker: _fake_ticker(None))

    pe, pb, roe = await sector_benchmarks.fetch_market_ratios("DELISTED")

    assert (pe, pb, roe) == (None, None, None)


@pytest.mark.asyncio
async def test_fetch_sector_benchmark_computes_median_across_peers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    peer_info = {
        "MSFT": {"trailingPE": 30.0, "priceToBook": 10.0, "returnOnEquity": 0.3},
        "GOOGL": {"trailingPE": 20.0, "priceToBook": 6.0, "returnOnEquity": 0.2},
        "META": {"trailingPE": 25.0, "priceToBook": 8.0, "returnOnEquity": 0.25},
        "NVDA": {"trailingPE": 40.0, "priceToBook": 20.0, "returnOnEquity": 0.5},
        "ORCL": {"trailingPE": 35.0, "priceToBook": 15.0, "returnOnEquity": 0.4},
    }

    def fake_ticker_for(ticker: str) -> object:
        if ticker == "AAPL":
            return _fake_ticker({"sector": "Technology"})
        return _fake_ticker(peer_info[ticker])

    monkeypatch.setattr(sector_benchmarks.yf, "Ticker", fake_ticker_for)

    benchmark = await sector_benchmarks.fetch_sector_benchmark("AAPL")

    assert benchmark.sector == "Technology"
    assert benchmark.median_pe == 30.0
    assert benchmark.median_pb == 10.0
    assert benchmark.median_roe == 0.3
    assert set(benchmark.peers_used) == set(peer_info)
    assert benchmark.errors == []


@pytest.mark.asyncio
async def test_fetch_sector_benchmark_degrades_on_unknown_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sector_benchmarks.yf, "Ticker", lambda ticker: _fake_ticker({"sector": "Widgets"})
    )

    benchmark = await sector_benchmarks.fetch_sector_benchmark("WIDGE")

    assert benchmark.median_pe is None
    assert benchmark.median_pb is None
    assert benchmark.median_roe is None
    assert benchmark.peers_used == []
    assert benchmark.errors


@pytest.mark.asyncio
async def test_fetch_sector_benchmark_tolerates_partial_peer_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_ticker_for(ticker: str) -> object:
        if ticker == "AAPL":
            return _fake_ticker({"sector": "Technology"})
        if ticker == "NVDA":
            raise RuntimeError("rate limited")
        return _fake_ticker({"trailingPE": 30.0, "priceToBook": 10.0, "returnOnEquity": 0.3})

    monkeypatch.setattr(sector_benchmarks.yf, "Ticker", fake_ticker_for)

    benchmark = await sector_benchmarks.fetch_sector_benchmark("AAPL")

    assert benchmark.median_pe == 30.0  # computed from the 4 surviving peers
    assert "NVDA" not in benchmark.peers_used
    assert any("NVDA" in e for e in benchmark.errors)
