from __future__ import annotations

from pydantic import BaseModel


class Document(BaseModel):
    """A retrieved or ingested document chunk."""

    id: str
    content: str
    metadata: dict[str, str] = {}


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Outgoing chat response body."""

    message: str
    sources: list[Document] = []
    conversation_id: str
