"""
Audit logging system using SQLAlchemy.
Connected to Neon Serverless PostgreSQL.
All queries use the ORM so they're database-agnostic.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from database.models import (
    AuditLog,
    PIIDetection,
    SecurityEvent,
    SessionLocal,
    init_db,
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """Database-agnostic audit logger using SQLAlchemy ORM."""

    def __init__(self):
        # Create tables on first use
        init_db()
        logger.info("Audit logger initialized (Neon Serverless PostgreSQL)")

    def _get_session(self):
        """Get a new database session."""
        return SessionLocal()

    @staticmethod
    def _hash_query(query: str) -> str:
        """Hash query for privacy-safe logging."""
        return hashlib.sha256(query.encode()).hexdigest()[:16]

    def log_interaction(
        self,
        session_id: str,
        query_sanitized: str,
        response_summary: str,
        tools_used: list[str],
        pii_detected: list[dict],
        compliance_flags: list[str],
        processing_time_ms: float,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """Log a complete agent interaction."""
        db = self._get_session()
        try:
            log_entry = AuditLog(
                timestamp=datetime.now(timezone.utc),
                session_id=session_id,
                event_type="agent_interaction",
                query_hash=self._hash_query(query_sanitized),
                query_sanitized=query_sanitized[:500],
                response_summary=response_summary[:1000],
                tools_used=json.dumps(tools_used),
                pii_detected=json.dumps(pii_detected),
                compliance_flags=json.dumps(compliance_flags),
                processing_time_ms=processing_time_ms,
                status=status,
                error_message=error_message,
            )
            db.add(log_entry)
            db.commit()
            logger.debug(f"Logged interaction for session {session_id}")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to log interaction: {e}")
        finally:
            db.close()

    def log_pii_detection(
        self,
        session_id: str,
        pii_type: str,
        action_taken: str,
        field_location: str = "input",
    ):
        """Log PII detection events."""
        db = self._get_session()
        try:
            detection = PIIDetection(
                timestamp=datetime.now(timezone.utc),
                session_id=session_id,
                pii_type=pii_type,
                action_taken=action_taken,
                field_location=field_location,
            )
            db.add(detection)
            db.commit()
            logger.debug(f"Logged PII detection: {pii_type} in {field_location}")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to log PII detection: {e}")
        finally:
            db.close()

    def log_security_event(
        self,
        session_id: str,
        event_type: str,
        severity: str,
        details: str,
        blocked: bool = False,
    ):
        """Log security events (prompt injection, etc.)."""
        db = self._get_session()
        try:
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc),
                session_id=session_id,
                event_type=event_type,
                severity=severity,
                details=details,
                blocked=blocked,
            )
            db.add(event)
            db.commit()
            logger.debug(f"Logged security event: {event_type} ({severity})")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Failed to log security event: {e}")
        finally:
            db.close()

    def get_session_logs(self, session_id: str) -> list[dict]:
        """Retrieve all logs for a session."""
        db = self._get_session()
        try:
            logs = (
                db.query(AuditLog)
                .filter(AuditLog.session_id == session_id)
                .order_by(AuditLog.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "session_id": log.session_id,
                    "event_type": log.event_type,
                    "query_hash": log.query_hash,
                    "query_sanitized": log.query_sanitized,
                    "response_summary": log.response_summary,
                    "tools_used": json.loads(log.tools_used) if log.tools_used else [],
                    "pii_detected": json.loads(log.pii_detected) if log.pii_detected else [],
                    "compliance_flags": json.loads(log.compliance_flags) if log.compliance_flags else [],
                    "processing_time_ms": log.processing_time_ms,
                    "status": log.status,
                    "error_message": log.error_message,
                }
                for log in logs
            ]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get session logs: {e}")
            return []
        finally:
            db.close()

    def get_security_summary(self, hours: int = 24) -> dict:
        """Get security event summary for monitoring."""
        db = self._get_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Count by severity
            severity_counts = (
                db.query(SecurityEvent.severity, func.count(SecurityEvent.id))
                .filter(SecurityEvent.timestamp >= cutoff)
                .group_by(SecurityEvent.severity)
                .all()
            )
            summary = {severity: count for severity, count in severity_counts}

            # Count blocked requests
            blocked_count = (
                db.query(func.count(SecurityEvent.id))
                .filter(
                    SecurityEvent.blocked == True,
                    SecurityEvent.timestamp >= cutoff,
                )
                .scalar()
            )
            summary["total_blocked"] = blocked_count or 0

            return summary
        except SQLAlchemyError as e:
            logger.error(f"Failed to get security summary: {e}")
            return {"total_blocked": 0}
        finally:
            db.close()

    def get_stats(self) -> dict:
        """Get overall statistics."""
        db = self._get_session()
        try:
            stats = {}

            # Total interactions
            stats["total_interactions"] = (
                db.query(func.count(AuditLog.id)).scalar() or 0
            )

            # Total PII detections
            stats["total_pii_detections"] = (
                db.query(func.count(PIIDetection.id)).scalar() or 0
            )

            # Total blocked requests
            stats["total_blocked_requests"] = (
                db.query(func.count(SecurityEvent.id))
                .filter(SecurityEvent.blocked == True)
                .scalar() or 0
            )

            # Average processing time
            avg_time = (
                db.query(func.avg(AuditLog.processing_time_ms))
                .filter(AuditLog.status == "success")
                .scalar()
            )
            stats["avg_processing_time_ms"] = round(float(avg_time), 2) if avg_time else 0

            # Recent activity (last 24h)
            cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            stats["interactions_last_24h"] = (
                db.query(func.count(AuditLog.id))
                .filter(AuditLog.timestamp >= cutoff_24h)
                .scalar() or 0
            )

            return stats
        except SQLAlchemyError as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_interactions": 0,
                "total_pii_detections": 0,
                "total_blocked_requests": 0,
                "avg_processing_time_ms": 0,
                "interactions_last_24h": 0,
            }
        finally:
            db.close()

    def get_recent_logs(self, limit: int = 50) -> list[dict]:
        """Get most recent audit logs (for dashboard)."""
        db = self._get_session()
        try:
            logs = (
                db.query(AuditLog)
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "session_id": log.session_id,
                    "status": log.status,
                    "tools_used": json.loads(log.tools_used) if log.tools_used else [],
                    "processing_time_ms": log.processing_time_ms,
                    "pii_count": len(json.loads(log.pii_detected)) if log.pii_detected else 0,
                }
                for log in logs
            ]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent logs: {e}")
            return []
        finally:
            db.close()

    def get_recent_security_events(self, limit: int = 50) -> list[dict]:
        """Get most recent security events (for dashboard)."""
        db = self._get_session()
        try:
            events = (
                db.query(SecurityEvent)
                .order_by(SecurityEvent.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": event.id,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "session_id": event.session_id,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "details": event.details,
                    "blocked": event.blocked,
                }
                for event in events
            ]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent security events: {e}")
            return []
        finally:
            db.close()


# Singleton instance
audit_logger = AuditLogger()