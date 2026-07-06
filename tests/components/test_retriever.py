from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.components import retriever as retriever_module
from app.components.retriever import WeaviateRetriever
from app.models import Document


class _FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]


@dataclass
class _FakeObject:
    uuid: str
    properties: dict[str, str]


@dataclass
class _FakeQueryResult:
    objects: list[_FakeObject]


class _FakeData:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, str]] = {}
        self.insert_calls = 0
        self.replace_calls = 0

    def exists(self, uuid: str) -> bool:
        return uuid in self.store

    def insert(self, *, properties: dict[str, str], uuid: str, vector: list[float]) -> None:
        assert uuid not in self.store
        self.store[uuid] = properties
        self.insert_calls += 1

    def replace(self, *, uuid: str, properties: dict[str, str], vector: list[float]) -> None:
        assert uuid in self.store
        self.store[uuid] = properties
        self.replace_calls += 1


def _matches_filter(filter_obj: object, properties: dict[str, str]) -> bool:
    """Evaluate a real weaviate.classes.query.Filter against fake stored properties --
    these are plain introspectable objects (`.target`/`.value` for a single equality
    filter, `.filters` for an AND-combination), so this can faithfully exercise the exact
    Filter objects WeaviateRetriever.retrieve actually builds, without a real connection."""
    combined = getattr(filter_obj, "filters", None)
    if combined is not None:
        return all(_matches_filter(f, properties) for f in combined)
    return properties.get(filter_obj.target) == filter_obj.value


class _FakeQuery:
    def __init__(self, data: _FakeData) -> None:
        self._data = data

    def near_vector(self, *, near_vector: list[float], limit: int, filters: object = None) -> _FakeQueryResult:
        objects = [_FakeObject(uuid=uuid, properties=props) for uuid, props in self._data.store.items()]
        if filters is not None:
            objects = [o for o in objects if _matches_filter(filters, o.properties)]
        return _FakeQueryResult(objects=objects[:limit])


class _FakeCollection:
    def __init__(self) -> None:
        self.data = _FakeData()
        self.query = _FakeQuery(self.data)


@dataclass
class _FakeCollectionsManager:
    created: dict[str, _FakeCollection] = field(default_factory=dict)
    create_calls: int = 0

    def exists(self, name: str) -> bool:
        return name in self.created

    def create(self, *, name: str, **kwargs: object) -> None:
        self.created[name] = _FakeCollection()
        self.create_calls += 1

    def get(self, name: str) -> _FakeCollection:
        return self.created[name]


class _FakeClient:
    def __init__(self) -> None:
        self.collections = _FakeCollectionsManager()


@pytest.fixture(autouse=True)
def _fake_client(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(retriever_module, "_client", client)
    monkeypatch.setattr(retriever_module, "_get_client", lambda: client)
    return client


def test_add_documents_creates_collection_if_not_exists(_fake_client: _FakeClient) -> None:
    retriever = WeaviateRetriever("TestCollection", _FakeEmbeddings())

    retriever.add_documents([Document(id="doc-1", content="hello world", metadata={"ticker": "AAPL"})])

    assert _fake_client.collections.create_calls == 1
    assert "TestCollection" in _fake_client.collections.created


def test_add_documents_does_not_recreate_existing_collection(_fake_client: _FakeClient) -> None:
    retriever = WeaviateRetriever("TestCollection", _FakeEmbeddings())
    retriever.add_documents([Document(id="doc-1", content="hello", metadata={})])
    retriever.add_documents([Document(id="doc-2", content="world", metadata={})])

    assert _fake_client.collections.create_calls == 1


def test_add_documents_is_idempotent_on_reingestion(_fake_client: _FakeClient) -> None:
    """Re-adding a document with the same id must overwrite in place, not duplicate --
    duplicate near-identical chunks would inflate retrieval and wreck RAGAS scoring."""
    retriever = WeaviateRetriever("TestCollection", _FakeEmbeddings())
    doc = Document(id="doc-1", content="original text", metadata={"ticker": "AAPL"})

    retriever.add_documents([doc])
    retriever.add_documents([Document(id="doc-1", content="updated text", metadata={"ticker": "AAPL"})])

    collection = _fake_client.collections.get("TestCollection")
    assert len(collection.data.store) == 1
    assert collection.data.insert_calls == 1
    assert collection.data.replace_calls == 1


def test_retrieve_returns_documents_from_near_vector_search(_fake_client: _FakeClient) -> None:
    retriever = WeaviateRetriever("TestCollection", _FakeEmbeddings())
    retriever.add_documents([Document(id="doc-1", content="apple risk factors", metadata={"ticker": "AAPL"})])

    results = retriever.retrieve("apple risk", k=5)

    assert len(results) == 1
    assert results[0].content == "apple risk factors"
    assert results[0].metadata["ticker"] == "AAPL"


def test_add_documents_retries_embedding_then_succeeds(
    _fake_client: _FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    class _FlakyEmbeddings(_FakeEmbeddings):
        def __init__(self) -> None:
            self.calls = 0

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.calls += 1
            if self.calls < 2:
                raise RuntimeError("rate limited")
            return super().embed_documents(texts)

    flaky = _FlakyEmbeddings()
    retriever = WeaviateRetriever("TestCollection", flaky)

    retriever.add_documents([Document(id="doc-1", content="hello", metadata={})])

    assert flaky.calls == 2
    assert len(_fake_client.collections.get("TestCollection").data.store) == 1


def test_add_documents_aborts_cleanly_after_exhausted_retries(
    _fake_client: _FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No fallback tier exists for embeddings -- exhausted retries must propagate and
    leave nothing written, rather than silently writing a partial/broken batch."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    class _AlwaysFailingEmbeddings(_FakeEmbeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("rate limited")

    retriever = WeaviateRetriever("TestCollection", _AlwaysFailingEmbeddings())

    with pytest.raises(RuntimeError, match="rate limited"):
        retriever.add_documents([Document(id="doc-1", content="hello", metadata={})])

    assert "TestCollection" not in _fake_client.collections.created or not _fake_client.collections.get(
        "TestCollection"
    ).data.store


def test_retrieve_applies_metadata_filters(_fake_client: _FakeClient) -> None:
    retriever = WeaviateRetriever("TestCollection", _FakeEmbeddings())
    retriever.add_documents(
        [
            Document(id="doc-aapl", content="apple text", metadata={"ticker": "AAPL"}),
            Document(id="doc-msft", content="microsoft text", metadata={"ticker": "MSFT"}),
        ]
    )

    results = retriever.retrieve("text", k=5, filters={"ticker": "AAPL"})

    assert len(results) == 1
    assert results[0].metadata["ticker"] == "AAPL"
