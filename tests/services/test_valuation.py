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


def test_compare_to_sector_excludes_negative_pe_from_comparison() -> None:
    """A negative P/E (a company with negative trailing earnings) isn't a meaningful
    valuation multiple to compare against a positive sector median -- caught in PR review:
    dividing a negative P/E by a positive median produces a negative ratio that could be
    misread as "deeply undervalued" when it actually reflects unprofitability, not a
    valuation signal."""
    result = compare_to_sector("AAPL", pe=-10.0, pb=5.0, roe=0.2, benchmark=_benchmark())

    assert result.vs_sector["pe"] is None
    assert "pe_below_sector" not in result.risk_flags
    assert "pe_above_sector" not in result.risk_flags
    # pb=5.0 vs median 5.0 alone drives the verdict once pe is excluded.
    assert result.valuation_verdict == "fairly_valued"


def test_compare_to_sector_excludes_negative_pb_from_comparison() -> None:
    result = compare_to_sector("AAPL", pe=20.0, pb=-5.0, roe=0.2, benchmark=_benchmark())

    assert result.vs_sector["pb"] is None
    assert "pb_below_sector" not in result.risk_flags


def test_compare_to_sector_still_compares_negative_roe() -> None:
    """ROE is a profitability signal, not a valuation multiple -- a negative ROE vs. a
    positive sector median is still meaningful information (the company is unprofitable
    relative to peers), so it must not be excluded the way negative P/E and P/B are."""
    result = compare_to_sector("AAPL", pe=20.0, pb=5.0, roe=-0.4, benchmark=_benchmark())

    assert result.vs_sector["roe"] == -2.0
    assert "roe_below_sector" in result.risk_flags
