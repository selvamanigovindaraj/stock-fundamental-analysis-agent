from __future__ import annotations

import pytest

from app.agents import valuation_graph
from app.models import SectorBenchmark


@pytest.mark.asyncio
async def test_run_valuation_calls_through_to_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_market_ratios(
        ticker: str,
    ) -> tuple[float | None, float | None, float | None]:
        assert ticker == "AAPL"
        return 20.0, 5.0, 0.2

    async def fake_fetch_sector_benchmark(ticker: str) -> SectorBenchmark:
        assert ticker == "AAPL"
        return SectorBenchmark(
            sector="Technology",
            median_pe=20.0,
            median_pb=5.0,
            median_roe=0.2,
            peers_used=["MSFT"],
            errors=[],
        )

    monkeypatch.setattr(valuation_graph, "fetch_market_ratios", fake_fetch_market_ratios)
    monkeypatch.setattr(valuation_graph, "fetch_sector_benchmark", fake_fetch_sector_benchmark)

    result = await valuation_graph.run_valuation("AAPL")

    assert result.ticker == "AAPL"
    assert result.valuation_verdict == "fairly_valued"
    assert result.vs_sector == {"pe": 1.0, "pb": 1.0, "roe": 1.0}
