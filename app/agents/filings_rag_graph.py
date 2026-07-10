from __future__ import annotations

from typing import TypedDict

import voyageai
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr

from app.config import get_settings
from app.models import Document, FilingsRAGAnswer
from app.services.guardrails import sanitize_ticker
from app.services.filings.retriever import FilingsRAGRetriever

_NO_RESULTS_ANSWER = "I couldn't find relevant information in the filings to answer this question."

# Voyage's rerank scores are roughly normalized 0-1; verified live against real chunks that
# genuinely-relevant content scores ~0.6-0.75 and irrelevant content scores ~0.3 for a typical
# query -- 0.5 is a reasonable cutoff, not an exact science. Tune if false-positive/negative
# rates turn out to matter in practice.
_RELEVANCE_THRESHOLD = 0.5


class FilingsRAGState(TypedDict):
    question: str
    ticker: str
    documents: list[Document]
    answer: str


_rerank_client: voyageai.AsyncClient | None = None
_generation_llm: ChatOpenAI | None = None


def _get_rerank_client() -> voyageai.AsyncClient:
    global _rerank_client
    if _rerank_client is None:
        _rerank_client = voyageai.AsyncClient(api_key=get_settings().voyage_api_key)
    return _rerank_client


def _get_generation_llm() -> ChatOpenAI:
    global _generation_llm
    if _generation_llm is None:
        settings = get_settings()
        _generation_llm = ChatOpenAI(
            model=settings.deepseek_model_generation,
            api_key=SecretStr(settings.deepseek_api_key),
            base_url=settings.deepseek_base_url,
        )
    return _generation_llm


async def _retrieve(state: FilingsRAGState) -> FilingsRAGState:
    documents = await FilingsRAGRetriever().retrieve(state["question"], ticker=state["ticker"])
    return {**state, "documents": documents}


async def _grade_documents(state: FilingsRAGState) -> FilingsRAGState:
    """Confirm retrieved chunks are actually relevant before generation, using Voyage's
    reranker rather than an LLM classifier -- one cheap, purpose-built API call instead of
    a structured-output round-trip."""
    documents = state["documents"]
    if not documents:
        return {**state, "documents": []}
    result = await _get_rerank_client().rerank(
        query=state["question"],
        documents=[doc.content for doc in documents],
        model=get_settings().voyage_rerank_model,
    )
    relevant_indices = {r.index for r in result.results if r.relevance_score >= _RELEVANCE_THRESHOLD}
    filtered = [doc for i, doc in enumerate(documents) if i in relevant_indices]
    return {**state, "documents": filtered}


def _generation_prompt(question: str, documents: list[Document]) -> str:
    citations = "\n\n".join(
        f"[{doc.metadata.get('form_type', '')} {doc.metadata.get('period', '')} "
        f"{doc.metadata.get('section', '')}]: {doc.content}"
        for doc in documents
    )
    return (
        f"Using only the filing excerpts below, answer the question. Cite the section "
        f"(e.g. form type, period, section) each part of your answer comes from.\n\n"
        f"Question: {question}\n\nExcerpts:\n{citations}"
    )


async def _generate(state: FilingsRAGState) -> FilingsRAGState:
    documents = state["documents"]
    if not documents:
        return {**state, "answer": _NO_RESULTS_ANSWER}
    response = await _get_generation_llm().ainvoke(_generation_prompt(state["question"], documents))
    return {**state, "answer": str(response.content)}


def build_filings_rag_graph() -> CompiledStateGraph:
    """DataIngestionAgent/Report-Writer-facing subgraph: retrieve -> grade_documents ->
    generate. Grading and generation both short-circuit (no LLM call) when there are no
    documents to work with."""
    graph = StateGraph(FilingsRAGState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("grade_documents", _grade_documents)
    graph.add_node("generate", _generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_edge("grade_documents", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


_compiled_graph = build_filings_rag_graph()


async def answer_filing_question(question: str, ticker: str) -> FilingsRAGAnswer:
    """Answer a natural-language question about `ticker`'s filings, with citations."""
    ticker = sanitize_ticker(ticker)
    result = await _compiled_graph.ainvoke(
        {"question": question, "ticker": ticker, "documents": [], "answer": ""}
    )
    return FilingsRAGAnswer(answer=result["answer"], citations=result["documents"])
