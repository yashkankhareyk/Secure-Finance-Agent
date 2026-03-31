"""
Fix 4 — Hybrid RAG Retrieval (BM25 + Dense Vector) with chunk metadata
Replaces: backend/rag/retriever.py

Changes vs original:
  • Adds BM25 keyword retrieval alongside dense vector search
  • Merges results using Reciprocal Rank Fusion (RRF)
  • Each retrieved chunk now exposes source, topic, date metadata
  • Requires: pip install rank-bm25

Why: Dense embeddings miss exact financial terms (CAGR, P/E, 401k).
     BM25 catches exact matches; fusion gives you the best of both.
"""

import logging
import math
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import settings

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False
    logger.warning(
        "rank-bm25 not installed — falling back to dense-only retrieval. "
        "Install with: pip install rank-bm25"
    )


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    return text.lower().split()


def _reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.
    Each item must have a unique "id" field.
    Returns items sorted by fused score descending.
    """
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
            items[item_id] = item

    fused = sorted(items.values(), key=lambda x: scores[x["id"]], reverse=True)
    for item in fused:
        item["rrf_score"] = round(scores[item["id"]], 6)
    return fused


class FinancialRetriever:
    """
    Hybrid retriever: BM25 keyword search + dense vector search, fused via RRF.
    Falls back to dense-only if rank-bm25 is not installed.
    """

    def __init__(self):
        # Dense embeddings (unchanged from original)
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("HuggingFace embeddings loaded")
        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            raise

        self.vector_store = Chroma(
            collection_name="financial_docs",
            embedding_function=self.embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )

        # BM25 index — rebuilt from ChromaDB on first use
        self._bm25: Optional["BM25Okapi"] = None
        self._bm25_docs: list[dict] = []   # parallel list of doc dicts

        logger.info(f"FinancialRetriever ready (hybrid={'yes' if _BM25_AVAILABLE else 'dense-only'})")

    # ── BM25 index management ──────────────────────────────────────────────────

    def _build_bm25_index(self):
        """Load all docs from ChromaDB and build a BM25 index."""
        if not _BM25_AVAILABLE:
            return
        try:
            collection = self.vector_store._collection
            result = collection.get(include=["documents", "metadatas"])
            docs = result.get("documents") or []
            metas = result.get("metadatas") or [{}] * len(docs)
            ids = result.get("ids") or [str(i) for i in range(len(docs))]

            if not docs:
                logger.debug("BM25: no documents to index yet")
                return

            self._bm25_docs = [
                {"id": ids[i], "content": docs[i], "metadata": metas[i]}
                for i in range(len(docs))
            ]
            tokenized = [_tokenize(d["content"]) for d in self._bm25_docs]
            self._bm25 = BM25Okapi(tokenized)
            logger.info(f"BM25 index built over {len(docs)} chunks")
        except Exception as e:
            logger.warning(f"BM25 index build failed: {e}")
            self._bm25 = None

    def _ensure_bm25(self):
        if _BM25_AVAILABLE and self._bm25 is None:
            self._build_bm25_index()

    def invalidate_bm25(self):
        """Call after ingesting new documents so BM25 is rebuilt next search."""
        self._bm25 = None
        self._bm25_docs = []

    # ── BM25 search ───────────────────────────────────────────────────────────

    def _bm25_search(self, query: str, k: int) -> list[dict]:
        self._ensure_bm25()
        if self._bm25 is None or not self._bm25_docs:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for rank, idx in enumerate(top_indices):
            if scores[idx] <= 0:
                continue
            doc = self._bm25_docs[idx].copy()
            doc["bm25_score"] = round(float(scores[idx]), 4)
            results.append(doc)
        return results

    # ── Dense search ──────────────────────────────────────────────────────────

    def _dense_search(self, query: str, k: int) -> list[dict]:
        try:
            raw = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
            results = []
            for doc, score in raw:
                doc_id = doc.metadata.get("id") or doc.page_content[:40]
                results.append({
                    "id": doc_id,
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "dense_score": round(score, 4),
                })
            return results
        except Exception as e:
            logger.error(f"Dense search error: {e}")
            return []

    # ── Public search API ─────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: int = 5,
        score_threshold: Optional[float] = None,
        return_metadata: bool = True,
    ) -> list[dict]:
        """
        Hybrid search: BM25 + dense vector, fused via RRF.

        Returns list of dicts with keys:
            content, metadata, rrf_score, source, topic, date_ingested
        """
        fetch_k = k * 2  # fetch more candidates before fusion

        dense_results = self._dense_search(query, fetch_k)

        if _BM25_AVAILABLE:
            bm25_results = self._bm25_search(query, fetch_k)
            # Assign stable IDs to BM25 results for RRF
            for doc in bm25_results:
                if "id" not in doc:
                    doc["id"] = doc["content"][:40]
            fused = _reciprocal_rank_fusion([dense_results, bm25_results])
        else:
            fused = dense_results
            for item in fused:
                item["rrf_score"] = item.get("dense_score", 0.0)

        # Apply score threshold
        if score_threshold is not None:
            fused = [d for d in fused if d.get("rrf_score", 0) >= score_threshold]

        # Trim to k
        fused = fused[:k]

        # Enrich with human-readable metadata fields
        output = []
        for doc in fused:
            meta = doc.get("metadata", {})
            output.append({
                "content": doc.get("content", ""),
                "metadata": meta,
                "relevance_score": doc.get("rrf_score", 0.0),
                # Convenience fields for the LLM / citations
                "source": meta.get("source_file", "knowledge base"),
                "topic": meta.get("topic", "general"),
                "date_ingested": meta.get("date_ingested", ""),
                "page": meta.get("page", ""),
                "section": meta.get("section_heading", ""),
            })

        logger.debug(f"Hybrid search returned {len(output)} results for: {query[:60]}")
        return output

    # ── Backward-compat helpers ───────────────────────────────────────────────

    def get_retriever(self, k: int = 5):
        """LangChain retriever interface (dense only, for chain compatibility)."""
        return self.vector_store.as_retriever(
            search_type="similarity", search_kwargs={"k": k}
        )

    def has_documents(self) -> bool:
        try:
            return self.vector_store._collection.count() > 0
        except Exception:
            return False

    def get_document_count(self) -> int:
        try:
            return self.vector_store._collection.count()
        except Exception:
            return 0


# Singleton
financial_retriever = FinancialRetriever()