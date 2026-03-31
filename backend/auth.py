"""
Fix 1 — Authentication Middleware
Adds JWT bearer token + API key auth to all routes.
Place this file at: backend/auth.py

Usage in main.py:
    from auth import require_auth
    @app.post("/chat")
    async def chat(request: ChatRequest, req: Request, _: str = Depends(require_auth)):
        ...
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ── JWT support (optional, falls back to opaque tokens) ───────────────────────
try:
    import jwt as pyjwt
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False
    logger.warning("PyJWT not installed — using opaque token auth only.")

# ── Configuration (read from env, never from code defaults in prod) ───────────
SECRET_KEY: str = os.environ.get("API_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "dev-secret-key-change-in-prod":
    if os.environ.get("DEBUG", "false").lower() != "true":
        raise RuntimeError(
            "API_SECRET_KEY env var must be set to a strong random value in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    SECRET_KEY = "dev-secret-key-change-in-prod"
    logger.warning("Running with default secret key — FOR DEVELOPMENT ONLY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ── Static API keys (comma-separated list in env var) ─────────────────────────
# Example: API_KEYS=key1,key2,key3
_RAW_API_KEYS = os.environ.get("API_KEYS", "")
VALID_API_KEYS: set[str] = {
    k.strip() for k in _RAW_API_KEYS.split(",") if k.strip()
}

# If no API keys configured, generate a temporary one on startup (dev only)
if not VALID_API_KEYS:
    _temp_key = secrets.token_hex(32)
    VALID_API_KEYS.add(_temp_key)
    logger.warning(
        f"No API_KEYS env var set. Temporary key for this session: {_temp_key}"
    )

bearer_scheme = HTTPBearer(auto_error=False)


# ── Token creation (for /auth/token endpoint) ─────────────────────────────────

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    if not _JWT_AVAILABLE:
        raise RuntimeError("PyJWT is required for JWT token creation. pip install PyJWT")
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_jwt(token: str) -> Optional[str]:
    """Verify a JWT and return the subject, or None if invalid."""
    if not _JWT_AVAILABLE:
        return None
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except pyjwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except pyjwt.InvalidTokenError as e:
        logger.debug(f"Invalid JWT: {e}")
        return None


# ── FastAPI dependency ─────────────────────────────────────────────────────────

async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """
    FastAPI dependency.  Accepts either:
      • A valid JWT bearer token (if PyJWT installed and JWT issued via /auth/token)
      • A valid static API key (set via API_KEYS env var)

    Returns the authenticated identity string (sub claim or "api-key-user").
    Raises HTTP 401 on failure.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 1. Try static API key first (constant-time comparison)
    if any(secrets.compare_digest(token, k) for k in VALID_API_KEYS):
        return "api-key-user"

    # 2. Try JWT
    if _JWT_AVAILABLE:
        subject = verify_jwt(token)
        if subject:
            return subject

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ── Optional: public /auth/token endpoint (add to main.py) ───────────────────

from pydantic import BaseModel

class TokenRequest(BaseModel):
    api_key: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


def get_token_router():
    """
    Returns an APIRouter with a /auth/token endpoint.
    Mount it in main.py:
        from auth import get_token_router
        app.include_router(get_token_router())
    """
    from fastapi import APIRouter
    router = APIRouter(tags=["auth"])

    @router.post("/auth/token", response_model=TokenResponse)
    async def issue_token(body: TokenRequest):
        """Exchange a static API key for a short-lived JWT."""
        if not any(secrets.compare_digest(body.api_key, k) for k in VALID_API_KEYS):
            raise HTTPException(status_code=401, detail="Invalid API key")
        token = create_access_token(subject="authenticated-user")
        return TokenResponse(
            access_token=token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    return router