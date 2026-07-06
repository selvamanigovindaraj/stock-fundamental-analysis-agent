from __future__ import annotations

import math

import pytest

from app.services.ratio_engine import RatioEngine
from tests.fixtures.financials import REFERENCE_CASES


@pytest.mark.parametrize("ticker, statements, expected", REFERENCE_CASES)
def test_compute_matches_reference_ratios(ticker, statements, expected) -> None:
    ratios = RatioEngine.compute(statements)

    assert ratios.ticker == ticker
    assert ratios.source == statements.source
    assert ratios.is_gaap == statements.is_gaap

    for field, expected_value in expected.items():
        actual_value = getattr(ratios, field)
        if math.isnan(expected_value):
            assert math.isnan(actual_value), f"{ticker}.{field} expected NaN, got {actual_value}"
        else:
            assert actual_value == pytest.approx(expected_value, rel=0.01), (
                f"{ticker}.{field} expected {expected_value}, got {actual_value}"
            )


def test_compute_ratio_fields_present() -> None:
    ratios = RatioEngine.compute(REFERENCE_CASES[0][1])
    expected_fields = REFERENCE_CASES[0][2].keys()
    for field in expected_fields:
        assert hasattr(ratios, field)


@pytest.mark.asyncio
async def test_compute_all_fetches_via_ingestion_then_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents import ingestion_graph

    _, statements, _ = REFERENCE_CASES[0]

    async def fake_run_ingestion(ticker: str):
        assert ticker == statements.ticker
        return statements

    monkeypatch.setattr(ingestion_graph, "run_ingestion", fake_run_ingestion)

    ratios = await RatioEngine.compute_all(statements.ticker)

    assert ratios.ticker == statements.ticker
    assert ratios.source == statements.source
