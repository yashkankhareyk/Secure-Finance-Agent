"""
RAG Retriever - searches the vector store for relevant financial information.
Uses langchain_huggingface (the official new package) instead of the
deprecated langchain_community.embeddings.HuggingFaceEmbeddings.
"""

import logging
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import settings

logger = logging.getLogger(__name__)


class FinancialRetriever:
    """Retrieves relevant financial documents from ChromaDB."""

    def __init__(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("HuggingFace embeddings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            raise

        self.vector_store = Chroma(
            collection_name="financial_docs",
            embedding_function=self.embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )
        logger.info(
            f"ChromaDB initialized at {settings.CHROMA_PERSIST_DIR}"
        )

    def search(
        self,
        query: str,
        k: int = 4,
        score_threshold: Optional[float] = None,
    ) -> list[dict]:
        """
        Search for relevant documents.

        Args:
            query: The search query string.
            k: Number of results to return.
            score_threshold: Minimum relevance score (0-1). None = no filter.

        Returns:
            List of dicts with keys: content, metadata, relevance_score.
        """
        try:
            results = self.vector_store.similarity_search_with_relevance_scores(
                query, k=k
            )

            documents = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": round(score, 4),
                }
                for doc, score in results
            ]

            # Apply threshold filter if specified
            if score_threshold is not None:
                documents = [
                    doc for doc in documents
                    if doc["relevance_score"] >= score_threshold
                ]

            logger.debug(
                f"Search returned {len(documents)} results for query: "
                f"{query[:50]}..."
            )
            return documents

        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []

    def get_retriever(self, k: int = 4):
        """Get a LangChain retriever for use in chains."""
        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k},
        )

    def has_documents(self) -> bool:
        """Check if vector store has any documents."""
        try:
            collection = self.vector_store._collection
            count = collection.count()
            logger.debug(f"Vector store document count: {count}")
            return count > 0
        except Exception as e:
            logger.warning(f"Could not check document count: {e}")
            return False

    def get_document_count(self) -> int:
        """Get total number of documents in vector store."""
        try:
            return self.vector_store._collection.count()
        except Exception:
            return 0


# Singleton
financial_retriever = FinancialRetriever()