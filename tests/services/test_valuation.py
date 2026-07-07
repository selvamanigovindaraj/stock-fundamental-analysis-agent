from __future__ import annotations

from app.models import SectorBenchmark
from app.services.valuation import compare_to_sector


def _benchmark(
    *, median_pe: float | None = 20.0, median_pb: float | None = 5.0, median_roe: float | None = 0.2
) -> SectorBenchmark:
    return SectorBenchmark(
        sector="Technology",
        median_pe=median_pe,
        median_pb=median_pb,
        median_roe=median_roe,
        peers_used=["MSFT"],
        errors=[],
    )


def test_compare_to_sector_fairly_valued_when_ratios_near_one() -> None:
    result = compare_to_sector("AAPL", pe=20.0, pb=5.0, roe=0.2, benchmark=_benchmark())

    assert result.valuation_verdict == "fairly_valued"
    assert result.vs_sector == {"pe": 1.0, "pb": 1.0, "roe": 1.0}
    assert result.risk_flags == []


def test_compare_to_sector_overvalued_when_pe_pb_well_above_sector() -> None:
    result = compare_to_sector("AAPL", pe=40.0, pb=15.0, roe=0.2, benchmark=_benchmark())

    assert result.valuation_verdict == "overvalued"
    assert "pe_above_sector" in result.risk_flags
    assert "pb_above_sector" in result.risk_flags


def test_compare_to_sector_undervalued_when_pe_pb_well_below_sector() -> None:
    result = compare_to_sector("AAPL", pe=5.0, pb=1.0, roe=0.2, benchmark=_benchmark())

    assert result.valuation_verdict == "undervalued"
    assert "pe_below_sector" in result.risk_flags
    assert "pb_below_sector" in result.risk_flags


def test_compare_to_sector_insufficient_data_when_everything_missing() -> None:
    result = compare_to_sector(
        "AAPL",
        pe=None,
        pb=None,
        roe=None,
        benchmark=_benchmark(median_pe=None, median_pb=None, median_roe=None),
    )

    assert result.valuation_verdict == "insufficient_data"
    assert result.vs_sector == {"pe": None, "pb": None, "roe": None}
    assert result.risk_flags == []


def test_compare_to_sector_tolerates_missing_pe_pb_using_roe_only() -> None:
    result = compare_to_sector(
        "AAPL", pe=None, pb=None, roe=0.5, benchmark=_benchmark(median_pe=None, median_pb=None)
    )

    assert result.valuation_verdict == "fairly_valued"
    assert result.vs_sector["roe"] == 2.5
    assert "roe_above_sector" in result.risk_flags
