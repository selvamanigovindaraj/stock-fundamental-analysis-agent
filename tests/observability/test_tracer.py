from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.observability import tracer as tracer_module
from app.observability.tracer import Tracer


def test_log_fallback_logs_locally_without_langsmith_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(tracer_module.get_settings(), "langsmith_api_key", "")
    fake_client_cls = MagicMock()
    monkeypatch.setattr(tracer_module.langsmith, "Client", fake_client_cls)

    with caplog.at_level(logging.WARNING):
        Tracer().log_fallback(ticker="AAPL", from_source="yfinance", to_source="edgartools", reason="timeout")

    assert "AAPL" in caplog.text
    assert "yfinance" in caplog.text
    assert "edgartools" in caplog.text
    fake_client_cls.assert_not_called()  # never touches LangSmith without a configured key


def test_log_fallback_calls_langsmith_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tracer_module.get_settings(), "langsmith_api_key", "fake-key")
    fake_client = MagicMock()
    monkeypatch.setattr(tracer_module.langsmith, "Client", MagicMock(return_value=fake_client))

    Tracer().log_fallback(ticker="MSFT", from_source="edgartools", to_source="sec_edgar", reason="rate limited")

    fake_client.create_run.assert_called_once()
    _, kwargs = fake_client.create_run.call_args
    assert kwargs["name"] == "ingestion_fallback"
    assert kwargs["inputs"] == {"ticker": "MSFT", "from_source": "edgartools", "to_source": "sec_edgar"}
    assert kwargs["error"] == "rate limited"


def test_log_fallback_never_raises_on_langsmith_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tracer_module.get_settings(), "langsmith_api_key", "fake-key")
    fake_client_cls = MagicMock(side_effect=RuntimeError("network down"))
    monkeypatch.setattr(tracer_module.langsmith, "Client", fake_client_cls)

    Tracer().log_fallback(ticker="TSLA", from_source="yfinance", to_source="edgartools", reason="outage")
