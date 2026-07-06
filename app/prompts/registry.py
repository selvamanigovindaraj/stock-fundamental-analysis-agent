from __future__ import annotations


class PromptRegistry:
    """Lookup and versioning for prompt templates."""

    def __init__(self) -> None:
        pass

    def get(self, name: str, version: str = "latest") -> str:
        """Return the prompt template registered under `name`."""
        raise NotImplementedError
