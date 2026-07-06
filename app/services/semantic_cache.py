from __future__ import annotations


class SemanticCache:
    """Caches query/response pairs keyed by semantic similarity."""

    def __init__(self) -> None:
        pass

    def get(self, query: str) -> str | None:
        """Return a cached response if a semantically similar query exists."""
        raise NotImplementedError

    def set(self, query: str, response: str) -> None:
        """Store a query/response pair in the cache."""
        raise NotImplementedError
