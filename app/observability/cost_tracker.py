from __future__ import annotations


class CostTracker:
    """Tracks token usage and estimated cost per request."""

    def __init__(self) -> None:
        pass

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for a model call."""
        raise NotImplementedError
