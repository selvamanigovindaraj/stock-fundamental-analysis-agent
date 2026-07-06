from __future__ import annotations

from langchain_core.tools import tool

from app.agents.filings_rag_graph import answer_filing_question


@tool
async def filings_rag_tool(question: str, ticker: str) -> str:
    """Answer a natural-language question about a company's 10-K/10-Q filings -- their
    Management Discussion & Analysis and Risk Factors disclosures -- grounded in retrieved
    filing excerpts with citations. Use this when you need to know what management said
    about a topic (strategy, risks, outlook) in their regulatory filings, as opposed to
    numeric fundamentals."""
    result = await answer_filing_question(question, ticker)
    if not result.citations:
        return result.answer

    citations = "; ".join(
        f"{doc.metadata.get('form_type', '')} {doc.metadata.get('period', '')} "
        f"{doc.metadata.get('section', '')} ({doc.metadata.get('filing_url', '')})"
        for doc in result.citations
    )
    return f"{result.answer}\n\nSources: {citations}"
