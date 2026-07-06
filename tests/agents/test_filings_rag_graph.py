from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.agents import filings_rag_graph
from app.models import Document
from app.services.filings.retriever import FilingsRAGRetriever


@dataclass
class _FakeRerankResult:
    index: int
    relevance_score: float


@dataclass
class _FakeRerankingObject:
    results: list[_FakeRerankResult]


class _FakeRerankClient:
    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.invoked = False
        self.last_call: dict[str, object] = {}

    async def rerank(self, *, query: str, documents: list[str], model: str) -> _FakeRerankingObject:
        self.invoked = True
        self.last_call = {"query": query, "documents": documents, "model": model}
        results = sorted(
            (_FakeRerankResult(index=i, relevance_score=s) for i, s in enumerate(self._scores)),
            key=lambda r: r.relevance_score,
            reverse=True,
        )
        return _FakeRerankingObject(results=results)


class _FakeGenerationLLM:
    def __init__(self, content: str = "the answer") -> None:
        self._content = content
        self.invoke_count = 0

    async def ainvoke(self, prompt: str) -> object:
        self.invoke_count += 1
        return type("Resp", (), {"content": self._content})()


def _docs(n: int) -> list[Document]:
    return [Document(id=f"d{i}", content=f"chunk {i}", metadata={"ticker": "AAPL"}) for i in range(n)]


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(filings_rag_graph, "_rerank_client", None)
    monkeypatch.setattr(filings_rag_graph, "_generation_llm", None)


@pytest.mark.asyncio
async def test_grade_documents_filters_out_irrelevant_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    documents = _docs(3)

    async def fake_retrieve(self: FilingsRAGRetriever, *args: object, **kwargs: object) -> list[Document]:
        return documents

    monkeypatch.setattr(FilingsRAGRetriever, "retrieve", fake_retrieve)

    rerank_client = _FakeRerankClient(scores=[0.74, 0.12, 0.66])  # index 1 below threshold
    generation_llm = _FakeGenerationLLM("final answer")
    monkeypatch.setattr(filings_rag_graph, "_rerank_client", rerank_client)
    monkeypatch.setattr(filings_rag_graph, "_generation_llm", generation_llm)

    result = await filings_rag_graph.answer_filing_question("What did AAPL say?", "AAPL")

    assert rerank_client.invoked is True
    assert rerank_client.last_call["query"] == "What did AAPL say?"
    assert rerank_client.last_call["documents"] == ["chunk 0", "chunk 1", "chunk 2"]
    assert len(result.citations) == 2
    assert {c.id for c in result.citations} == {"d0", "d2"}
    assert result.answer == "final answer"


@pytest.mark.asyncio
async def test_empty_retrieval_short_circuits_without_calling_rerank_or_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_retrieve(self: FilingsRAGRetriever, *args: object, **kwargs: object) -> list[Document]:
        return []

    monkeypatch.setattr(FilingsRAGRetriever, "retrieve", fake_retrieve)

    rerank_client = _FakeRerankClient(scores=[])
    generation_llm = _FakeGenerationLLM()
    monkeypatch.setattr(filings_rag_graph, "_rerank_client", rerank_client)
    monkeypatch.setattr(filings_rag_graph, "_generation_llm", generation_llm)

    result = await filings_rag_graph.answer_filing_question("What did AAPL say?", "AAPL")

    assert rerank_client.invoked is False
    assert generation_llm.invoke_count == 0
    assert result.citations == []
    assert result.answer != ""


@pytest.mark.asyncio
async def test_all_chunks_below_relevance_threshold_skips_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = _docs(2)

    async def fake_retrieve(self: FilingsRAGRetriever, *args: object, **kwargs: object) -> list[Document]:
        return documents

    monkeypatch.setattr(FilingsRAGRetriever, "retrieve", fake_retrieve)

    rerank_client = _FakeRerankClient(scores=[0.1, 0.2])
    generation_llm = _FakeGenerationLLM()
    monkeypatch.setattr(filings_rag_graph, "_rerank_client", rerank_client)
    monkeypatch.setattr(filings_rag_graph, "_generation_llm", generation_llm)

    result = await filings_rag_graph.answer_filing_question("What did AAPL say?", "AAPL")

    assert generation_llm.invoke_count == 0
    assert result.citations == []
