"""
OTP (One-Time Password) Service for Admin Password Reset

Generates, stores, and verifies 6-digit OTPs.
Storage: in-memory dict with TTL (suitable for single-instance deployments).
For multi-instance, switch to Redis-backed storage via REDIS_URL.
"""

import logging
import secrets
import time
from dataclasses import dataclass

import bcrypt

from app.config import OTP_MAX_ATTEMPTS, OTP_TTL_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class OTPRecord:
    """Stored OTP record with metadata."""
    otp_hash: str
    created_at: float
    attempts: int = 0
    used: bool = False


# In-memory OTP store (keyed by email). For production multi-instance,
# replace with Redis using REDIS_URL.
_otp_store: dict[str, OTPRecord] = {}


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp: str) -> str:
    """Bcrypt-hash an OTP for secure storage."""
    return bcrypt.hashpw(otp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_otp_hash(otp: str, otp_hash: str) -> bool:
    """Verify an OTP against its bcrypt hash."""
    try:
        return bcrypt.checkpw(otp.encode("utf-8"), otp_hash.encode("utf-8"))
    except Exception:
        return False


def store_otp(email: str, otp: str) -> None:
    """
    Store a hashed OTP for the given email. Overwrites any existing OTP.
    """
    _cleanup_expired()
    _otp_store[email.lower()] = OTPRecord(
        otp_hash=_hash_otp(otp),
        created_at=time.time(),
    )
    logger.info("OTP stored", extra={"email": email})


def verify_otp(email: str, otp: str) -> bool:
    """
    Verify an OTP for the given email.

    - Enforces max attempts (OTP_MAX_ATTEMPTS).
    - Enforces TTL (OTP_TTL_SECONDS).
    - Invalidates the OTP on successful verification.
    - Returns True if valid, False otherwise.
    """
    key = email.lower()
    record = _otp_store.get(key)

    if not record:
        logger.warning("OTP verify: no OTP found", extra={"email": email})
        return False

    # Check if already used
    if record.used:
        logger.warning("OTP verify: already used", extra={"email": email})
        return False

    # Check TTL
    if time.time() - record.created_at > OTP_TTL_SECONDS:
        logger.warning("OTP verify: expired", extra={"email": email})
        del _otp_store[key]
        return False

    # Check max attempts
    record.attempts += 1
    if record.attempts > OTP_MAX_ATTEMPTS:
        logger.warning("OTP verify: max attempts exceeded", extra={"email": email})
        del _otp_store[key]
        return False

    # Verify hash
    if _verify_otp_hash(otp, record.otp_hash):
        record.used = True
        del _otp_store[key]  # Invalidate after use
        logger.info("OTP verified successfully", extra={"email": email})
        return True

    logger.warning(
        "OTP verify: wrong code",
        extra={"email": email, "attempt": record.attempts},
    )
    return False


def _cleanup_expired() -> None:
    """Remove expired OTP records from in-memory store."""
    now = time.time()
    expired = [
        k for k, v in _otp_store.items()
        if now - v.created_at > OTP_TTL_SECONDS
    ]
    for k in expired:
        del _otp_store[k]
