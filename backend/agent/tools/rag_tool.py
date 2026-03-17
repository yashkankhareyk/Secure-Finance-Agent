"""
RAG Tool - Searches financial knowledge base for relevant information.
"""

import logging
from langchain_core.tools import tool
from rag.retriever import financial_retriever

logger = logging.getLogger(__name__)


@tool
def search_financial_knowledge(query: str) -> str:
    """
    Search the financial knowledge base for information about
    investment strategies, retirement planning, risk management,
    tax strategies, and compliance regulations.

    Use this tool when the user asks about:
    - Investment strategies or asset allocation
    - Retirement planning (401k, IRA, etc.)
    - Risk metrics (beta, sharpe ratio, etc.)
    - Tax-efficient investing
    - Financial regulations and compliance
    - General financial education topics

    Args:
        query: The search query about financial topics
    """
    try:
        results = financial_retriever.search(query, k=3)

        if not results:
            return "No relevant information found in the knowledge base. I'll provide general guidance based on my training."

        # Format results
        formatted = []
        for i, r in enumerate(results, 1):
            source = r["metadata"].get("topic", "general")
            score = r["relevance_score"]
            formatted.append(
                f"**Source {i}** (topic: {source}, relevance: {score}):\n{r['content']}"
            )

        return "\n\n---\n\n".join(formatted)

    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return f"Knowledge base search encountered an error. Please try rephrasing your question."