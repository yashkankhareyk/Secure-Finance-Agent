"""
Fix 5 — Cross-Encoder Re-Ranking
New file: backend/rag/reranker.py

After hybrid retrieval returns top-k candidates, a cross-encoder
scores each (query, chunk) pair and re-orders them.
This dramatically improves precision for financial terminology.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2  (free, ~80MB, CPU-friendly)
Install: pip install sentence-transformers  (already in requirements.txt)

Usage — drop into rag_tool.py:
    from rag.reranker import reranker
    results = financial_retriever.search(query, k=10)
    results = reranker.rerank(query, results, top_n=4)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Cross-encoder model — lazy loaded on first use
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """
    Wraps a sentence-transformers CrossEncoder for re-ranking RAG results.
    Falls back gracefully (returns original order) if model can't load.
    """

    def __init__(self, model_name: str = _MODEL_NAME):
        self._model_name = model_name
        self._model = None          # lazy init
        self._available = None      # None = not yet checked

    def _load(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name, max_length=512)
            self._available = True
            logger.info(f"CrossEncoder re-ranker loaded: {self._model_name}")
        except Exception as e:
            self._available = False
            logger.warning(
                f"CrossEncoder not available ({e}). "
                "Re-ranking disabled — results will use RRF order. "
                "Ensure sentence-transformers>=2.0 is installed."
            )
        return self._available

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_n: int = 4,
        content_key: str = "content",
    ) -> list[dict]:
        """
        Re-rank documents using the cross-encoder.

        Args:
            query:       The user's query string.
            documents:   List of dicts with at least a `content_key` field.
            top_n:       How many top results to return after re-ranking.
            content_key: Key in each dict that holds the text to score.

        Returns:
            Top-n documents sorted by cross-encoder score (highest first),
            with a new "rerank_score" key added to each.
        """
        if not documents:
            return documents

        # Always fall back gracefully
        if not self._load():
            return documents[:top_n]

        pairs = [(query, doc.get(content_key, "")) for doc in documents]

        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.error(f"CrossEncoder prediction failed: {e}")
            return documents[:top_n]

        # Attach scores and sort
        scored = sorted(
            zip(scores, documents),
            key=lambda x: x[0],
            reverse=True,
        )

        result = []
        for score, doc in scored[:top_n]:
            doc = doc.copy()
            doc["rerank_score"] = round(float(score), 4)
            result.append(doc)

        logger.debug(
            f"Re-ranked {len(documents)} → {len(result)} docs. "
            f"Top score: {result[0]['rerank_score'] if result else 'n/a'}"
        )
        return result


# Singleton — shared across requests
reranker = CrossEncoderReranker()