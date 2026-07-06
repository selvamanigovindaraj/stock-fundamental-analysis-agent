from __future__ import annotations

import weaviate
import weaviate.classes as wvc
from langchain_core.embeddings import Embeddings
from tenacity import retry, stop_after_attempt, wait_exponential
from weaviate.util import generate_uuid5

from app.config import get_settings
from app.models import Document


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _embed_documents(embeddings: Embeddings, texts: list[str]) -> list[list[float]]:
    # No fallback tier exists for embeddings (unlike the 3-tier fundamentals pipeline) --
    # retry on transient/rate-limit failures; if all attempts are exhausted the exception
    # propagates and add_documents aborts cleanly before writing anything (safe to retry
    # the whole call later since upserts are idempotent).
    return embeddings.embed_documents(texts)


_client: weaviate.WeaviateClient | None = None


def _get_client() -> weaviate.WeaviateClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = weaviate.connect_to_weaviate_cloud(
            cluster_url=settings.weaviate_url,
            auth_credentials=weaviate.auth.Auth.api_key(settings.weaviate_api_key),
        )
    return _client


class WeaviateRetriever:
    """Semantic retriever backed by a Weaviate Cloud collection. Vectors are always
    computed client-side by the injected `embeddings` client, never Weaviate's built-in
    vectorizer -- this keeps the same embeddings integration usable both here and (e.g.)
    wrapped for RAGAS evaluation elsewhere."""

    def __init__(self, class_name: str, embeddings: Embeddings) -> None:
        self._class_name = class_name
        self._embeddings = embeddings

    def _collection(self) -> weaviate.collections.Collection:
        client = _get_client()
        if not client.collections.exists(self._class_name):
            client.collections.create(
                name=self._class_name,
                properties=[wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT)],
                vector_config=wvc.config.Configure.Vectors.self_provided(),
            )
        return client.collections.get(self._class_name)

    def add_documents(self, documents: list[Document]) -> None:
        """Embed and upsert documents. Re-adding a document with the same `id` overwrites
        it in place instead of duplicating, so re-running ingestion is safe."""
        if not documents:
            return
        collection = self._collection()
        vectors = _embed_documents(self._embeddings, [doc.content for doc in documents])
        for document, vector in zip(documents, vectors, strict=True):
            uuid = generate_uuid5(document.id)
            properties = {"content": document.content, **document.metadata}
            if collection.data.exists(uuid):
                collection.data.replace(uuid=uuid, properties=properties, vector=vector)
            else:
                collection.data.insert(properties=properties, uuid=uuid, vector=vector)

    def retrieve(
        self, query: str, k: int = 6, filters: dict[str, str] | None = None
    ) -> list[Document]:
        """Embed `query` and run a near-vector search, optionally filtered by exact-match
        metadata properties (e.g. `{"ticker": "AAPL"}`)."""
        collection = self._collection()
        vector = self._embeddings.embed_query(query)

        weaviate_filter = None
        for key, value in (filters or {}).items():
            condition = wvc.query.Filter.by_property(key).equal(value)
            weaviate_filter = condition if weaviate_filter is None else weaviate_filter & condition

        result = collection.query.near_vector(near_vector=vector, limit=k, filters=weaviate_filter)
        documents = []
        for obj in result.objects:
            properties = dict(obj.properties)
            content = str(properties.pop("content", ""))
            documents.append(
                Document(
                    id=str(obj.uuid),
                    content=content,
                    metadata={key: str(value) for key, value in properties.items()},
                )
            )
        return documents
