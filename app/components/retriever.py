from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Document


class WeaviateRetriever:
    """Semantic retriever backed by a Weaviate Cloud collection."""

    def __init__(self, class_name: str) -> None:
        """Initialise the Weaviate Cloud client and target collection."""
        pass

    def retrieve(self, query: str, k: int = 6) -> list[Document]:
        """Run a semantic (near-text) search against the collection."""
        raise NotImplementedError

    def add_documents(self, documents: list[Document]) -> None:
        """Upsert documents (with embeddings) into the collection."""
        raise NotImplementedError
