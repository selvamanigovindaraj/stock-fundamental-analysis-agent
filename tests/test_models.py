from __future__ import annotations

import pytest

from app.models import AnalystReport


def _report(**overrides: object) -> AnalystReport:
    fields: dict[str, object] = {
        "ticker": "AAPL",
        "executive_summary": "ok",
        "financial_health": "ok",
        "valuation_assessment": "ok",
        "risk_factors": ["default risk"],
        "key_themes": ["default theme"],
        "disclaimer": "ok",
    }
    fields.update(overrides)
    return AnalystReport(**fields)


@pytest.mark.parametrize("field", ["risk_factors", "key_themes"])
def test_list_fields_pass_through_a_real_list(field: str) -> None:
    report = _report(**{field: ["a", "b"]})
    assert getattr(report, field) == ["a", "b"]


@pytest.mark.parametrize("field", ["risk_factors", "key_themes"])
def test_list_fields_coerce_a_json_stringified_list(field: str) -> None:
    """DeepSeek's structured output sometimes returns a JSON-stringified array instead of
    a real list (found via live verify-agent: 5/10 real ticker reports hit this and crashed
    with a Pydantic ValidationError after ~20s of prior agent work)."""
    report = _report(**{field: '["Valuation premium", "Regulatory risk"]'})
    assert getattr(report, field) == ["Valuation premium", "Regulatory risk"]


@pytest.mark.parametrize("field", ["risk_factors", "key_themes"])
def test_list_fields_coerce_a_numbered_multiline_string(field: str) -> None:
    report = _report(**{field: "1. First point.\n2. Second point.\n3. Third point."})
    assert getattr(report, field) == ["First point.", "Second point.", "Third point."]


@pytest.mark.parametrize("field", ["risk_factors", "key_themes"])
def test_list_fields_wrap_a_single_sentence_string(field: str) -> None:
    report = _report(**{field: "Just one plain sentence with no separators."})
    assert getattr(report, field) == ["Just one plain sentence with no separators."]
