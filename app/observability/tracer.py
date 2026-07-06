from __future__ import annotations


class Tracer:
    """Emits spans/traces for agent and tool calls."""

    def __init__(self) -> None:
        pass

    def start_span(self, name: str) -> None:
        """Start a trace span."""
        raise NotImplementedError
