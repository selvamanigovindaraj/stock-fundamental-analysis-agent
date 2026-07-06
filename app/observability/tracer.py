from __future__ import annotations

import logging

import langsmith

from app.config import get_settings

logger = logging.getLogger(__name__)


class Tracer:
    """Emits spans/traces for agent and tool calls."""

    def __init__(self) -> None:
        pass

    def start_span(self, name: str) -> None:
        """Start a trace span."""
        raise NotImplementedError

    def log_fallback(self, *, ticker: str, from_source: str, to_source: str, reason: str) -> None:
        """Record an ingestion fallback transition. Logs locally if LangSmith isn't configured;
        a LangSmith outage never breaks ingestion."""
        settings = get_settings()
        if not settings.langsmith_api_key:
            logger.warning(
                "ingestion fallback for %s: %s -> %s (%s)", ticker, from_source, to_source, reason
            )
            return
        try:
            client = langsmith.Client(api_key=settings.langsmith_api_key)
            client.create_run(
                name="ingestion_fallback",
                run_type="chain",
                inputs={"ticker": ticker, "from_source": from_source, "to_source": to_source},
                error=reason,
                project_name=settings.langsmith_project,
            )
        except Exception:  # noqa: BLE001 - a LangSmith outage must never break ingestion
            logger.warning(
                "ingestion fallback for %s: %s -> %s (%s) [LangSmith logging failed]",
                ticker,
                from_source,
                to_source,
                reason,
            )
