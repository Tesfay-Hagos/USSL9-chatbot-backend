"""
Audit Logging for GDPR / European Government Compliance

Logs security-relevant events: auth, admin actions, data access.
Structured JSON format for SIEM integration and retention policies.
IPs are SHA-256 hashed before storage (GDPR Art. 25 — data minimisation).
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import AUDIT_LOG_ENABLED, AUDIT_LOG_PATH, IP_HASH_SALT

logger = logging.getLogger("audit")


def _hash_ip(ip: str | None) -> str | None:
    """SHA-256 hash an IP address with salt for GDPR-compliant anonymisation."""
    if not ip:
        return None
    return hashlib.sha256(f"{IP_HASH_SALT}:{ip}".encode()).hexdigest()[:16]


def _audit_event(
    event_type: str,
    action: str,
    user: str | None = None,
    ip: str | None = None,
    resource: str | None = None,
    details: dict | None = None,
    success: bool = True,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build a structured audit event. IPs are hashed for GDPR compliance."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "action": action,
        "user": user,
        "ip_hash": _hash_ip(ip),
        "resource": resource,
        "details": details or {},
        "success": success,
        "correlation_id": correlation_id,
    }


def _emit(event: dict[str, Any]) -> None:
    """Emit audit event to configured sink."""
    if not AUDIT_LOG_ENABLED:
        return
    line = json.dumps(event, default=str) + "\n"
    if AUDIT_LOG_PATH:
        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            logger.warning("Audit log write failed: %s", e)
    else:
        logger.info("AUDIT: %s", line.strip())


def log_login(user: str, ip: str | None, success: bool, correlation_id: str | None = None) -> None:
    """Log authentication attempt."""
    _emit(_audit_event(
        event_type="auth",
        action="login",
        user=user,
        ip=ip,
        success=success,
        correlation_id=correlation_id,
    ))


def log_admin_action(
    user: str,
    action: str,
    resource: str | None = None,
    details: dict | None = None,
    ip: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Log admin API action (store create/delete, document upload, etc.)."""
    _emit(_audit_event(
        event_type="admin",
        action=action,
        user=user,
        ip=ip,
        resource=resource,
        details=details,
        success=True,
        correlation_id=correlation_id,
    ))


def log_data_access(
    resource: str,
    action: str,
    ip: str | None = None,
    details: dict | None = None,
    correlation_id: str | None = None,
) -> None:
    """Log data/knowledge base access (chat, domain list, etc.)."""
    _emit(_audit_event(
        event_type="data_access",
        action=action,
        ip=ip,
        resource=resource,
        details=details or {},
        success=True,
        correlation_id=correlation_id,
    ))
