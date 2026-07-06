from __future__ import annotations

import pytest

from app.agents.tools import filings_rag_tool as tool_module
from app.models import Document, FilingsRAGAnswer


@pytest.mark.asyncio
async def test_filings_rag_tool_includes_answer_and_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_answer(question: str, ticker: str) -> FilingsRAGAnswer:
        assert question == "What did AAPL say about AI?"
        assert ticker == "AAPL"
        return FilingsRAGAnswer(
            answer="AAPL emphasized AI investment.",
            citations=[
                Document(
                    id="d1",
                    content="...",
                    metadata={
                        "form_type": "10-K",
                        "period": "2024-09-28",
                        "section": "mdna",
                        "filing_url": "https://example.com/aapl.htm",
                    },
                )
            ],
        )

    monkeypatch.setattr(tool_module, "answer_filing_question", fake_answer)

    result = await tool_module.filings_rag_tool.ainvoke(
        {"question": "What did AAPL say about AI?", "ticker": "AAPL"}
    )

    assert "AAPL emphasized AI investment." in result
    assert "https://example.com/aapl.htm" in result


@pytest.mark.asyncio
async def test_filings_rag_tool_handles_no_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_answer(question: str, ticker: str) -> FilingsRAGAnswer:
        return FilingsRAGAnswer(answer="No relevant information found.", citations=[])

    monkeypatch.setattr(tool_module, "answer_filing_question", fake_answer)

    result = await tool_module.filings_rag_tool.ainvoke({"question": "anything", "ticker": "ZZZZ"})

    assert result == "No relevant information found."
