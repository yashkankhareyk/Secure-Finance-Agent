"""
FastAPI Backend - Main application entry point.
Handles HTTP endpoints, security middleware, and agent orchestration.
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
from agent.graph import run_agent
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

# Rate limiting store (in-memory, simple)
_rate_limit_store: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("Starting Secure Financial Advisory Agent...")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"LLM Model: {settings.LLM_MODEL}")

    # Seed sample data if vector store is empty
    if not financial_retriever.has_documents():
        logger.info("Seeding sample financial data...")
        seed_sample_data()
        logger.info("Sample data seeded successfully")
    else:
        logger.info("Vector store already contains documents")

    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Secure Financial Advisory Agent",
    description=(
        "AI-powered financial advisory agent with privacy protection, "
        "regulatory compliance, and real-time market data."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

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


# --- Rate Limiting ---

def check_rate_limit(client_ip: str) -> bool:
    """Simple in-memory rate limiter."""
    now = time.time()
    window = 60  # 1 minute window

    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = []

    # Clean old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < window
    ]

    if len(_rate_limit_store[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
        return False

    _rate_limit_store[client_ip].append(now)
    return True


# --- API Endpoints ---

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

    Flow:
    1. Rate limit check
    2. Prompt injection detection
    3. PII detection and anonymization
    4. Agent processing
    5. Output sanitization
    6. Audit logging
    """
    start_time = time.time()

    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    # Get client IP for rate limiting
    client_ip = req.client.host if req.client else "unknown"

    # 1. Rate limit check
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before sending more requests.",
        )

    # 2. Prompt injection detection
    guard_result = prompt_guard.check(request.message)

    if not guard_result["safe"]:
        # Log security event
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

    # 3. PII detection and anonymization on input
    sanitized_message, pii_detections = pii_detector.anonymize(
        guard_result["sanitized_input"],
        operator="replace",
    )

    # Log PII detections
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
    # Validate file type
    allowed_types = {".pdf", ".txt", ".md"}
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_ext}' not supported. Allowed: {allowed_types}",
        )

    # Validate file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    # Save file
    save_path = settings.FINANCIAL_REPORTS_DIR / file.filename
    with open(save_path, "wb") as f:
        f.write(content)

    # Ingest into vector store
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