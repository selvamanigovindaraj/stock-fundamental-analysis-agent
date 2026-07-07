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


@pytest.mark.parametrize("field", ["risk_factors", "key_themes"])
def test_list_fields_do_not_corrupt_text_starting_with_a_form_number(field: str) -> None:
    """The bullet/number-stripping regex must not treat "10-K"/"10-Q" (or a date like
    "2026-07-07") at the start of a line as a list marker -- caught in PR review: the
    original `^[-*\\d]+[.)]?\\s*` pattern stripped "10-" off "10-K reports show high risk",
    corrupting it to "K reports show high risk"."""
    report = _report(
        **{field: "10-K reports show high risk.\n2026-07-07 filing flagged a new item."}
    )
    assert getattr(report, field) == [
        "10-K reports show high risk.",
        "2026-07-07 filing flagged a new item.",
    ]


@pytest.mark.parametrize("field", ["risk_factors", "key_themes"])
def test_list_fields_coerce_none_to_an_empty_list(field: str) -> None:
    """DeepSeek's structured output can return `null` for these fields entirely (not just a
    malformed string) -- must coerce to an empty list rather than passing None through to
    Pydantic's `list[str]` validation, which would raise (caught in PR review)."""
    report = _report(**{field: None})
    assert getattr(report, field) == []
