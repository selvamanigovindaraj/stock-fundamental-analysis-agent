from __future__ import annotations

from typing import Literal

from app.models import SectorBenchmark, ValuationResult

_ABOVE_THRESHOLD = 1.5
_BELOW_THRESHOLD = 0.5
_OVERVALUED_THRESHOLD = 1.2
_UNDERVALUED_THRESHOLD = 0.8


def _ratio(
    value: float | None, median: float | None, *, allow_negative: bool = True
) -> float | None:
    if value is None or median is None or median == 0:
        return None
    if not allow_negative and (value < 0 or median < 0):
        # A negative P/E or P/B (e.g. a company with negative trailing earnings) isn't a
        # meaningful valuation multiple to compare against a sector median -- the resulting
        # ratio would misrepresent unprofitability as a valuation signal.
        return None
    return value / median


def _risk_flags(vs_sector: dict[str, float | None]) -> list[str]:
    flags = []
    for key, ratio in vs_sector.items():
        if ratio is None:
            continue
        if ratio > _ABOVE_THRESHOLD:
            flags.append(f"{key}_above_sector")
        elif ratio < _BELOW_THRESHOLD:
            flags.append(f"{key}_below_sector")
    return flags


def _verdict(
    vs_sector: dict[str, float | None],
) -> Literal["undervalued", "fairly_valued", "overvalued", "insufficient_data"]:
    if all(ratio is None for ratio in vs_sector.values()):
        return "insufficient_data"

    # P/E and P/B are valuation multiples (direction is meaningful: low = cheap); ROE is a
    # profitability signal, not a multiple, so it doesn't drive over/undervalued direction.
    multiples = [ratio for k in ("pe", "pb") if (ratio := vs_sector[k]) is not None]
    if not multiples:
        return "fairly_valued"  # only ROE available -- have data, but no valuation-direction signal

    average = sum(multiples) / len(multiples)
    if average < _UNDERVALUED_THRESHOLD:
        return "undervalued"
    if average > _OVERVALUED_THRESHOLD:
        return "overvalued"
    return "fairly_valued"


def compare_to_sector(
    ticker: str,
    pe: float | None,
    pb: float | None,
    roe: float | None,
    benchmark: SectorBenchmark,
) -> ValuationResult:
    """Deterministic comparison of a ticker's P/E, P/B, and ROE against its sector-peer
    median benchmark -- no LLM call, this is a numeric comparison, not a language task."""
    vs_sector: dict[str, float | None] = {
        # ROE (a profitability signal, not a valuation multiple) keeps allow_negative=True --
        # a negative ROE vs. a positive sector median is still meaningful information.
        "pe": _ratio(pe, benchmark.median_pe, allow_negative=False),
        "pb": _ratio(pb, benchmark.median_pb, allow_negative=False),
        "roe": _ratio(roe, benchmark.median_roe),
    }
    return ValuationResult(
        ticker=ticker,
        valuation_verdict=_verdict(vs_sector),
        vs_sector=vs_sector,
        risk_flags=_risk_flags(vs_sector),
    )
