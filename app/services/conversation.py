from __future__ import annotations


class ConversationStore:
    """Persists and retrieves multi-turn conversation history."""

    def __init__(self) -> None:
        pass

    def append(self, conversation_id: str, role: str, content: str) -> None:
        """Append a message to the conversation history."""
        raise NotImplementedError

    def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        """Return the full conversation history."""
        raise NotImplementedError
