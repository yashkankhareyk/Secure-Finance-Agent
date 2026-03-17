"""
SQLAlchemy ORM models for the audit database.
Configured for Neon Serverless PostgreSQL.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    Index,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class AuditLog(Base):
    """Stores every agent interaction for regulatory compliance."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    session_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, default="agent_interaction")
    query_hash = Column(String(16))
    query_sanitized = Column(Text)
    response_summary = Column(Text)
    tools_used = Column(Text)  # JSON string
    pii_detected = Column(Text)  # JSON string
    compliance_flags = Column(Text)  # JSON string
    processing_time_ms = Column(Float)
    status = Column(String(20), default="success")
    error_message = Column(Text)

    __table_args__ = (
        Index("idx_audit_session_time", "session_id", "timestamp"),
    )


class PIIDetection(Base):
    """Tracks all PII detection events."""
    __tablename__ = "pii_detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    session_id = Column(String(100), nullable=False, index=True)
    pii_type = Column(String(50), nullable=False)
    action_taken = Column(String(50), nullable=False)
    field_location = Column(String(20))


class SecurityEvent(Base):
    """Logs security incidents (prompt injection, abuse, etc.)."""
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    session_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    details = Column(Text)
    blocked = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_security_severity_time", "severity", "timestamp"),
    )


# --- Neon Serverless PostgreSQL Engine & Session Setup ---

def get_engine():
    """
    Create database engine for Neon Serverless PostgreSQL.

    Neon-specific optimizations:
    - pool_pre_ping: Handles Neon's connection suspension after idle timeout
    - pool_recycle: Prevents stale connections (Neon suspends after ~5min idle)
    - pool_size: Keep small — Neon free tier allows limited concurrent connections
    - sslmode=require: Enforced by Neon (should be in DATABASE_URL)
    """
    db_url = settings.DATABASE_URL

    engine = create_engine(
        db_url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=300,  # Recycle every 5 min (Neon suspends idle connections)
        pool_pre_ping=True,  # Verify connection is alive before using (critical for Neon)
    )

    return engine


# Create engine and session factory
engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db_session():
    """
    Get a database session.
    Use as context manager:
        with get_db_session() as session:
            session.query(...)
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()