"""
Fix 4 + 5 — Updated rag_tool.py
Replaces: backend/agent/tools/rag_tool.py

Changes vs original:
  • Uses financial_retriever.search() (hybrid) instead of simple similarity_search
  • Passes results through reranker before building context
  • Adds source citations and metadata to the tool output so the LLM can cite them
"""

import logging
from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_financial_knowledge(query: str) -> str:
    """
    Search the financial knowledge base using hybrid retrieval + re-ranking.
    Returns relevant financial information with source citations.
    """
    from rag.retriever import financial_retriever
    from rag.reranker import reranker

    # Step 1: Hybrid retrieval — fetch more candidates than we need
    candidates = financial_retriever.search(query, k=10)

    if not candidates:
        return (
            "No relevant information found in the knowledge base. "
            "I'll answer based on general financial knowledge."
        )

    # Step 2: Re-rank with cross-encoder for precision
    top_docs = reranker.rerank(query, candidates, top_n=4)

    # Step 3: Format results with source metadata for the LLM
    context_parts = []
    for i, doc in enumerate(top_docs, 1):
        source = doc.get("source", "knowledge base")
        topic = doc.get("topic", "")
        section = doc.get("section", "")
        score = doc.get("rerank_score") or doc.get("relevance_score", 0)

        header_parts = [f"[{i}]"]
        if topic:
            header_parts.append(f"Topic: {topic}")
        if source and source != "seed_data":
            header_parts.append(f"Source: {source}")
        if section:
            header_parts.append(f"Section: {section[:60]}")
        header_parts.append(f"Relevance: {score:.2f}")

        context_parts.append(" | ".join(header_parts))
        context_parts.append(doc["content"])
        context_parts.append("")  # blank line between chunks

    return "\n".join(context_parts)