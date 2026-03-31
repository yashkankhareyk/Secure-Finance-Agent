"""
FastAPI Backend - Main application entry point.
Handles HTTP endpoints, security middleware, and agent orchestration.

CHANGED:
- settings.validate_database_url() and settings.ensure_directories()
  moved here into lifespan() so imports never raise.
- initialize_agent() called in lifespan() for eager graph startup.
- Rate limiter is now proxy-aware (honors X-Forwarded-For).
- Rate limiter uses a cleanup strategy safe for long-running processes.
"""

import time
import uuid
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings
from agent.graph import run_agent, initialize_agent
from privacy.pii_detector import pii_detector
from privacy.prompt_guard import prompt_guard
from privacy.output_sanitizer import output_sanitizer
from database.audit_logger import audit_logger
from rag.ingest import document_ingestor, seed_sample_data
from rag.retriever import financial_retriever

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting store (in-memory, single-process)
# NOTE: For multi-worker/multi-container deployments replace with Redis.
#       e.g. pip install redis and use a shared Redis key per IP.
# ---------------------------------------------------------------------------
_rate_limit_store: dict[str, list[float]] = {}
_rate_limit_last_cleanup: float = time.time()
_RATE_LIMIT_CLEANUP_INTERVAL = 300  # clean up stale IPs every 5 minutes


def _get_client_ip(req: Request) -> str:
    """
    Return the real client IP, honoring reverse-proxy headers.
    X-Forwarded-For is set by Render, HuggingFace Spaces, Vercel, etc.
    Falls back to direct connection IP.
    """
    # X-Forwarded-For may contain a comma-separated list; take the first (originating) IP
    forwarded_for = req.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Fallback for CF/nginx single-header proxies
    real_ip = req.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return req.client.host if req.client else "unknown"


def check_rate_limit(client_ip: str) -> bool:
    """
    Sliding-window in-memory rate limiter.
    Periodically purges stale entries to avoid unbounded memory growth.
    """
    global _rate_limit_last_cleanup
    now = time.time()
    window = 60  # 1-minute window

    # Periodic cleanup of IPs with no recent activity
    if now - _rate_limit_last_cleanup > _RATE_LIMIT_CLEANUP_INTERVAL:
        stale = [ip for ip, times in _rate_limit_store.items()
                 if not any(now - t < window for t in times)]
        for ip in stale:
            del _rate_limit_store[ip]
        _rate_limit_last_cleanup = now

    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = []

    # Evict timestamps outside the current window
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < window
    ]

    if len(_rate_limit_store[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
        return False

    _rate_limit_store[client_ip].append(now)
    return True


# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting Secure Financial Advisory Agent...")

    # 1. Validate config (raises clearly if DATABASE_URL is missing)
    settings.validate_database_url()

    # 2. Ensure data directories exist
    settings.ensure_directories()

    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"LLM Model: {settings.LLM_MODEL}")

    # 3. Eagerly build agent graph + DB connection pool
    #    Errors surface here at startup rather than on the first request.
    logger.info("Initializing agent graph...")
    initialize_agent()

    # 4. Seed sample RAG data if vector store is empty
    if not financial_retriever.has_documents():
        logger.info("Seeding sample financial data...")
        seed_sample_data()
        logger.info("Sample data seeded successfully")
    else:
        logger.info("Vector store already contains documents")

    logger.info("Startup complete.")
    yield

    # Shutdown
    logger.info("Shutting down...")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Secure Financial Advisory Agent",
    description=(
        "AI-powered financial advisory agent with privacy protection, "
        "regulatory compliance, and real-time market data."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",
        "https://*.hf.space",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is a good asset allocation strategy for retirement?",
                "session_id": "user-123",
            }
        }


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list[str]
    route: str
    security: dict
    processing_time_ms: float
    disclaimer_added: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_provider: str
    documents_loaded: int


class UploadResponse(BaseModel):
    filename: str
    chunks_created: int
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    stats = document_ingestor.get_collection_stats()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_provider=f"{settings.LLM_PROVIDER}/{settings.LLM_MODEL}",
        documents_loaded=stats.get("total_documents", 0),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Main chat endpoint.
    Flow: rate limit → prompt guard → PII anonymize → agent → sanitize → audit log
    """
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())

    # Proxy-aware client IP
    client_ip = _get_client_ip(req)

    # 1. Rate limit
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before sending more requests.",
        )

    # 2. Prompt injection detection
    guard_result = prompt_guard.check(request.message)

    if not guard_result["safe"]:
        for threat in guard_result["threats"]:
            audit_logger.log_security_event(
                session_id=session_id,
                event_type=threat["type"],
                severity=threat["severity"],
                details=threat["detail"],
                blocked=True,
            )

        logger.warning(
            f"Blocked unsafe input (session: {session_id}): "
            f"{[t['type'] for t in guard_result['threats']]}"
        )

        processing_time = (time.time() - start_time) * 1000
        return ChatResponse(
            response=(
                "I'm unable to process this request as it appears to contain "
                "content outside my scope as a financial advisory assistant. "
                "I'm here to help with investment questions, market data, "
                "financial calculations, and compliance guidance. "
                "How can I assist you with your financial needs?"
            ),
            session_id=session_id,
            tools_used=["security_block"],
            route="blocked",
            security={
                "input_safe": False,
                "threats_detected": len(guard_result["threats"]),
                "threat_types": [t["type"] for t in guard_result["threats"]],
            },
            processing_time_ms=round(processing_time, 2),
            disclaimer_added=False,
        )

    # 3. PII detection and anonymization
    sanitized_message, pii_detections = pii_detector.anonymize(
        guard_result["sanitized_input"],
        operator="replace",
    )

    for detection in pii_detections:
        audit_logger.log_pii_detection(
            session_id=session_id,
            pii_type=detection["entity_type"],
            action_taken="anonymized_input",
            field_location="input",
        )

    # 4. Run the agent
    try:
        agent_result = run_agent(
            query=sanitized_message,
            session_id=session_id,
        )
    except Exception as e:
        logger.error(f"Agent error (session: {session_id}): {e}")
        processing_time = (time.time() - start_time) * 1000
        return ChatResponse(
            response=(
                "I apologize, but I encountered an error processing your request. "
                "Please try again or rephrase your question."
            ),
            session_id=session_id,
            tools_used=["error"],
            route="error",
            security={"input_safe": True, "pii_found_in_input": len(pii_detections)},
            processing_time_ms=round(processing_time, 2),
            disclaimer_added=False,
        )

    # 5. Output sanitization
    sanitized_output = output_sanitizer.sanitize(
        text=agent_result["response"],
        add_disclaimer=True,
        check_pii=True,
        session_id=session_id,
    )

    processing_time = (time.time() - start_time) * 1000

    # 6. Audit logging
    audit_logger.log_interaction(
        session_id=session_id,
        query_sanitized=sanitized_message[:200],
        response_summary=sanitized_output["text"][:200],
        tools_used=agent_result.get("tools_used", []),
        pii_detected=pii_detections + sanitized_output.get("pii_found", []),
        compliance_flags=sanitized_output.get("modifications", []),
        processing_time_ms=processing_time,
    )

    return ChatResponse(
        response=sanitized_output["text"],
        session_id=session_id,
        tools_used=agent_result.get("tools_used", []),
        route=agent_result.get("route", "unknown"),
        security={
            "input_safe": True,
            "pii_found_in_input": len(pii_detections),
            "pii_found_in_output": len(sanitized_output.get("pii_found", [])),
            "output_modifications": sanitized_output.get("modifications", []),
        },
        processing_time_ms=round(processing_time, 2),
        disclaimer_added=sanitized_output.get("disclaimer_added", False),
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload a financial document for RAG ingestion."""
    allowed_types = {".pdf", ".txt", ".md"}
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_ext}' not supported. Allowed: {allowed_types}",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    save_path = settings.FINANCIAL_REPORTS_DIR / file.filename
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        chunks = document_ingestor.ingest_file(str(save_path))
        return UploadResponse(
            filename=file.filename,
            chunks_created=chunks,
            status="success",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    audit_stats = audit_logger.get_stats()
    doc_stats = document_ingestor.get_collection_stats()
    security_summary = audit_logger.get_security_summary(24)
    return {
        "audit": audit_stats,
        "documents": doc_stats,
        "security_24h": security_summary,
    }


@app.get("/compliance/rules")
async def get_compliance_rules():
    """Get current compliance rules."""
    import yaml
    rules_file = settings.COMPLIANCE_RULES_DIR / "rules.yaml"
    if rules_file.exists():
        with open(rules_file) as f:
            return yaml.safe_load(f)
    return {"message": "No custom rules configured, using defaults."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )