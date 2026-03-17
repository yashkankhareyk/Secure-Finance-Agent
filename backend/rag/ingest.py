"""
Document ingestion pipeline for RAG.
Processes financial PDFs and text files into ChromaDB vector store.
Uses free sentence-transformers for embeddings (no API cost).
"""

import os
import logging
from pathlib import Path
from typing import Optional
import hashlib

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_chroma import Chroma

from langchain_huggingface import HuggingFaceEmbeddings

from config import settings

logger = logging.getLogger(__name__)


class DocumentIngestor:
    """Ingests financial documents into ChromaDB for RAG retrieval."""

    def __init__(self):
        # Use free local embeddings (no API key needed)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        self.vector_store = Chroma(
            collection_name="financial_docs",
            embedding_function=self.embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )

        self._ingested_hashes: set = set()

    def _file_hash(self, filepath: str) -> str:
        """Generate hash for deduplication."""
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def ingest_file(self, filepath: str, metadata: Optional[dict] = None) -> int:
        """
        Ingest a single file into the vector store.

        Returns number of chunks created.
        """
        filepath = str(filepath)
        file_hash = self._file_hash(filepath)

        if file_hash in self._ingested_hashes:
            logger.info(f"File already ingested: {filepath}")
            return 0

        # Load document based on extension
        ext = Path(filepath).suffix.lower()
        if ext == ".pdf":
            loader = PyPDFLoader(filepath)
        elif ext in (".txt", ".md"):
            loader = TextLoader(filepath)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return 0

        try:
            documents = loader.load()
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return 0

        # Add metadata
        for doc in documents:
            doc.metadata["source_file"] = Path(filepath).name
            doc.metadata["file_hash"] = file_hash
            if metadata:
                doc.metadata.update(metadata)

        # Split into chunks
        chunks = self.text_splitter.split_documents(documents)

        if not chunks:
            logger.warning(f"No chunks generated from {filepath}")
            return 0

        # Add to vector store
        self.vector_store.add_documents(chunks)
        self._ingested_hashes.add(file_hash)

        logger.info(f"Ingested {len(chunks)} chunks from {filepath}")
        return len(chunks)

    def ingest_directory(self, directory: Optional[str] = None) -> dict:
        """
        Ingest all supported files from a directory.

        Returns summary of ingestion.
        """
        if directory is None:
            directory = str(settings.FINANCIAL_REPORTS_DIR)

        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return {"files_processed": 0, "total_chunks": 0, "errors": []}

        results = {
            "files_processed": 0,
            "total_chunks": 0,
            "errors": [],
        }

        supported_extensions = {".pdf", ".txt", ".md"}

        for filepath in sorted(dir_path.iterdir()):
            if filepath.suffix.lower() in supported_extensions:
                try:
                    chunks = self.ingest_file(str(filepath))
                    results["files_processed"] += 1
                    results["total_chunks"] += chunks
                except Exception as e:
                    results["errors"].append(f"{filepath.name}: {str(e)}")

        logger.info(
            f"Ingestion complete: {results['files_processed']} files, "
            f"{results['total_chunks']} chunks"
        )
        return results

    def ingest_text(self, text: str, metadata: Optional[dict] = None) -> int:
        """Ingest raw text directly (for sample data)."""
        from langchain.schema import Document

        doc = Document(page_content=text, metadata=metadata or {})
        chunks = self.text_splitter.split_documents([doc])

        if chunks:
            self.vector_store.add_documents(chunks)

        return len(chunks)

    def get_collection_stats(self) -> dict:
        """Get statistics about the vector store."""
        try:
            collection = self.vector_store._collection
            count = collection.count()
            return {
                "total_documents": count,
                "collection_name": "financial_docs",
                "persist_directory": settings.CHROMA_PERSIST_DIR,
            }
        except Exception as e:
            return {"error": str(e)}


def seed_sample_data():
    """Seed the vector store with sample financial knowledge."""
    ingestor = DocumentIngestor()

    sample_documents = [
        {
            "text": """
            Asset Allocation Strategies for 2024

            The traditional 60/40 portfolio (60% stocks, 40% bonds) has been
            a cornerstone of investment strategy. However, with changing market
            conditions, many advisors now recommend:

            - Conservative: 30% stocks, 50% bonds, 20% alternatives
            - Moderate: 50% stocks, 30% bonds, 20% alternatives
            - Aggressive: 70% stocks, 15% bonds, 15% alternatives

            Key considerations:
            1. Risk tolerance assessment
            2. Time horizon to retirement
            3. Current market conditions
            4. Tax implications
            5. Liquidity needs

            Diversification across asset classes remains the primary risk
            management strategy. No single asset class consistently outperforms.
            """,
            "metadata": {"topic": "asset_allocation", "year": "2024"},
        },
        {
            "text": """
            Retirement Planning Fundamentals

            The 4% Rule: You can safely withdraw 4% of your retirement
            portfolio in the first year, then adjust for inflation each year.

            Retirement Account Types:
            - 401(k): Employer-sponsored, pre-tax contributions, $23,000 limit (2024)
            - Roth IRA: After-tax contributions, tax-free growth, $7,000 limit (2024)
            - Traditional IRA: Pre-tax contributions, $7,000 limit (2024)
            - SEP IRA: For self-employed, up to 25% of income

            Social Security:
            - Full retirement age: 67 (for those born after 1960)
            - Can claim early at 62 (reduced benefits)
            - Delayed to 70 (increased benefits ~8% per year)

            Target savings: 10-15% of pre-tax income annually
            Target retirement savings: 10-12x final salary
            """,
            "metadata": {"topic": "retirement_planning", "year": "2024"},
        },
        {
            "text": """
            Understanding Market Risk Metrics

            Beta: Measures a stock's volatility relative to the market.
            - Beta > 1: More volatile than market
            - Beta < 1: Less volatile than market
            - Beta = 1: Moves with market

            Sharpe Ratio: Risk-adjusted return measurement.
            Formula: (Portfolio Return - Risk Free Rate) / Portfolio Std Dev
            - Above 1.0: Good risk-adjusted returns
            - Above 2.0: Very good
            - Above 3.0: Excellent

            Standard Deviation: Measures investment volatility.
            Higher std dev = higher risk/potential return.

            Maximum Drawdown: Largest peak-to-trough decline.
            Important for understanding worst-case scenarios.

            Value at Risk (VaR): Maximum expected loss at a confidence level.
            Example: 95% VaR of $10,000 means 95% chance you won't lose
            more than $10,000 in a given period.
            """,
            "metadata": {"topic": "risk_metrics", "year": "2024"},
        },
        {
            "text": """
            Tax-Efficient Investment Strategies

            Tax-Loss Harvesting: Selling losing investments to offset gains.
            - Can offset up to $3,000 of ordinary income per year
            - Excess losses carry forward indefinitely
            - Watch the wash-sale rule (30-day window)

            Tax-Advantaged Account Placement:
            - Tax-inefficient (bonds, REITs) → Tax-deferred accounts
            - Tax-efficient (index funds, growth stocks) → Taxable accounts
            - Tax-free growth (Roth) → Highest expected growth assets

            Capital Gains Tax Rates (2024):
            - Short-term (< 1 year): Ordinary income rates (10-37%)
            - Long-term (> 1 year): 0%, 15%, or 20%
            - Net Investment Income Tax: Additional 3.8% for high earners

            Municipal Bonds: Interest is federal tax-free
            (and state tax-free if in your state).
            """,
            "metadata": {"topic": "tax_strategies", "year": "2024"},
        },
        {
            "text": """
            SEC Compliance and Fiduciary Standards

            Fiduciary Duty: Financial advisors must act in the client's
            best interest, not their own.

            Key Regulations:
            - Securities Act of 1933: Requires registration of securities
            - Securities Exchange Act of 1934: Governs secondary trading
            - Investment Advisers Act of 1940: Regulates investment advisors
            - Dodd-Frank Act (2010): Enhanced financial regulation
            - Regulation Best Interest (Reg BI): Broker-dealer standard

            Suitability Requirements:
            1. Customer's investment profile must be documented
            2. Recommendations must be suitable for the customer
            3. Conflicts of interest must be disclosed
            4. Excessive trading (churning) is prohibited

            Know Your Customer (KYC):
            - Identity verification
            - Financial situation assessment
            - Investment objectives documentation
            - Risk tolerance evaluation
            """,
            "metadata": {"topic": "compliance", "year": "2024"},
        },
    ]

    total_chunks = 0
    for doc in sample_documents:
        chunks = ingestor.ingest_text(doc["text"], doc["metadata"])
        total_chunks += chunks

    logger.info(f"Seeded {total_chunks} chunks of sample financial data")
    return total_chunks


# Singleton
document_ingestor = DocumentIngestor()