"""
Fix 6 — Secure File Upload Validator
New file: backend/upload_security.py

Drop-in replacement for the naive file checks in main.py /upload endpoint.
Covers:
  • MIME type validation (magic bytes, not just extension)
  • File size cap (configurable via env var)
  • Safe filename sanitization (no path traversal)
  • Basic malware hook placeholder (easy to wire in ClamAV or VirusTotal)

Usage in main.py:
    from upload_security import validate_upload
    @app.post("/upload")
    async def upload_document(file: UploadFile = File(...), ...):
        content, safe_name = await validate_upload(file)
        # write content to disk under safe_name...
"""

import os
import re
import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024

# Allowed (extension → expected magic bytes prefix)
ALLOWED_TYPES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".txt": (),        # no fixed magic; validated by UTF-8 decode below
    ".md":  (),        # same as .txt
}

# ── Magic-byte helpers ────────────────────────────────────────────────────────

def _check_magic(content: bytes, ext: str) -> bool:
    """Verify file starts with the expected magic bytes for its extension."""
    magic_list = ALLOWED_TYPES.get(ext, ())
    if not magic_list:
        # Text files: try UTF-8 decode on first 1 KB
        try:
            content[:1024].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return any(content.startswith(magic) for magic in magic_list)


def _safe_filename(original: str) -> str:
    """
    Strip directory components, replace unsafe chars, preserve extension.
    e.g. "../../etc/passwd" → "______etc_passwd"  (no extension → rejected upstream)
    """
    # Take only the basename
    name = Path(original).name
    # Replace anything that isn't alphanumeric, dot, dash, or underscore
    name = re.sub(r"[^\w.\-]", "_", name)
    # Collapse multiple dots to prevent extension confusion
    name = re.sub(r"\.{2,}", ".", name)
    # Max filename length
    if len(name) > 128:
        stem = Path(name).stem[:120]
        suffix = Path(name).suffix
        name = stem + suffix
    return name


# ── Main validator ────────────────────────────────────────────────────────────

async def validate_upload(file: UploadFile) -> tuple[bytes, str]:
    """
    Validate an uploaded file for security.

    Returns:
        (content_bytes, safe_filename)

    Raises:
        HTTPException 400 on any validation failure.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # 1. Extension check
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {list(ALLOWED_TYPES.keys())}",
        )

    # 2. Read content (size enforced server-side)
    content = await file.read()

    # 3. Size check
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 4. Magic-byte / encoding check
    if not _check_magic(content, ext):
        raise HTTPException(
            status_code=400,
            detail=(
                f"File content does not match extension '{ext}'. "
                "Possible file type mismatch or corruption."
            ),
        )

    # 5. Safe filename
    safe_name = _safe_filename(file.filename)

    # 6. Malware scan hook (plug in ClamAV / VirusTotal here)
    _malware_scan_hook(content, safe_name)

    logger.info(f"Upload validated: {safe_name} ({len(content)} bytes, ext={ext})")
    return content, safe_name


def _malware_scan_hook(content: bytes, filename: str):
    """
    Placeholder for antivirus scanning.
    To enable ClamAV scanning, install pyclamd and uncomment below:

        import pyclamd
        cd = pyclamd.ClamdUnixSocket()
        result = cd.scan_stream(content)
        if result:
            raise HTTPException(status_code=400, detail="File failed malware scan.")
    """
    pass   # No-op by default — replace with your scanner of choice