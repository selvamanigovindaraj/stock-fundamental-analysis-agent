from __future__ import annotations


def record_feedback(conversation_id: str, rating: int, comment: str | None = None) -> None:
    """Persist user feedback for a conversation turn."""
    raise NotImplementedError
