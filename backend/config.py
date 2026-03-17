"""
Configuration management for the Secure Financial Advisory Agent.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # --- Paths ---
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    FINANCIAL_REPORTS_DIR = DATA_DIR / "financial_reports"
    COMPLIANCE_RULES_DIR = DATA_DIR / "compliance_rules"
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chroma_db"))

    # --- Database (Neon Serverless PostgreSQL) ---
    # Format: postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    @property
    def is_postgres(self) -> bool:
        """Always True — Neon is PostgreSQL."""
        return True

    @property
    def is_neon(self) -> bool:
        """Check if using Neon serverless."""
        return "neon.tech" in self.DATABASE_URL

    def validate_database_url(self):
        """Ensure DATABASE_URL is set and points to Neon."""
        if not self.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Set it to your Neon connection string: "
                "postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require"
            )
        if not self.DATABASE_URL.startswith("postgresql"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string. "
                "Got: " + self.DATABASE_URL[:20] + "..."
            )

    # --- LLM Provider ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # openai, ollama, groq
    LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Groq (free tier)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    # OpenRouter (alternative hosted provider)
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://api.openrouter.ai")

    # --- Application ---
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # --- Security ---
    API_SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-prod")
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

    # --- CORS ---
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.FINANCIAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.COMPLIANCE_RULES_DIR.mkdir(parents=True, exist_ok=True)
        Path(cls.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_llm_config(cls) -> dict:
        """Return LLM configuration based on provider."""
        if cls.LLM_PROVIDER == "openai":
            return {
                "provider": "openai",
                "model": cls.LLM_MODEL,
                "api_key": cls.OPENAI_API_KEY,
            }
        elif cls.LLM_PROVIDER == "ollama":
            return {
                "provider": "ollama",
                "model": cls.LLM_MODEL,
                "base_url": cls.OLLAMA_BASE_URL,
            }
        elif cls.LLM_PROVIDER == "openrouter":
            return {
                "provider": "openrouter",
                "model": cls.LLM_MODEL,
                "api_key": cls.OPENROUTER_API_KEY,
                "base_url": cls.OPENROUTER_BASE_URL,
            }
        elif cls.LLM_PROVIDER == "groq":
            return {
                "provider": "groq",
                "model": cls.LLM_MODEL,
                "api_key": cls.GROQ_API_KEY,
            }
        else:
            raise ValueError(f"Unknown LLM provider: {cls.LLM_PROVIDER}")


settings = Settings()
settings.validate_database_url()
settings.ensure_directories()