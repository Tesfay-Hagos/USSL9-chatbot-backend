"""
Admin Password Reset via Email OTP (DB-backed)

Two-step flow:
1. POST /password-reset/request — sends OTP to the admin's email via Brevo
2. POST /password-reset/confirm — verifies OTP and updates bcrypt password hash in DB

GDPR Note: admin email is not logged; only hashed IP is recorded in audit.
"""

import logging

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.core.audit import log_admin_action
from app.core.database import get_db
from app.core.models import AdminUser
from app.core.utils import get_client_ip
from app.services.email_sender import send_otp_email
from app.services.otp import generate_otp, store_otp, verify_otp

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──

class PasswordResetRequest(BaseModel):
    """Step 1: request a password reset OTP."""
    email: str = Field(min_length=5, max_length=254)


class PasswordResetConfirm(BaseModel):
    """Step 2: confirm OTP and set new password."""
    email: str = Field(min_length=5, max_length=254)
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=200)


class MessageResponse(BaseModel):
    message: str


# ── Endpoints ──

@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(body: PasswordResetRequest, request: Request):
    """
    Request a password reset. Sends a 6-digit OTP to the admin's email.

    Always returns 200 regardless of whether the email matches, to prevent
    email enumeration attacks.
    """
    ip = get_client_ip(request)
    corr_id = getattr(request.state, "correlation_id", None)

    # Log the attempt (no email in logs for GDPR)
    log_admin_action(
        user="anonymous",
        action="password_reset_request",
        ip=ip,
        correlation_id=corr_id,
    )

    # Look up admin user by email in the database
    async with get_db() as db:
        result = await db.execute(
            select(AdminUser).where(
                AdminUser.email == body.email.lower(),
                AdminUser.is_active == True,  # noqa: E712
            )
        )
        admin_user = result.scalars().first()

    if admin_user:
        otp = generate_otp()
        store_otp(body.email, otp)
        sent = await send_otp_email(body.email, otp)
        if not sent:
            logger.error("Failed to send OTP email")
            # Still return 200 to prevent enumeration
    else:
        logger.info("Password reset requested for non-admin email (ignored)")

    return MessageResponse(
        message="If the email is registered, a verification code has been sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(body: PasswordResetConfirm, request: Request):
    """
    Confirm password reset with OTP and set a new password.

    Updates the password_hash in the AdminUser database table.
    """
    ip = get_client_ip(request)
    corr_id = getattr(request.state, "correlation_id", None)

    # Verify OTP
    if not verify_otp(body.email, body.otp):
        log_admin_action(
            user="anonymous",
            action="password_reset_confirm_failed",
            ip=ip,
            correlation_id=corr_id,
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new one.",
        )

    # Hash new password
    new_hash = bcrypt.hashpw(
        body.new_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    # Update password in database
    async with get_db() as db:
        result = await db.execute(
            update(AdminUser)
            .where(AdminUser.email == body.email.lower())
            .values(password_hash=new_hash)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Admin user not found")

    log_admin_action(
        user=body.email.lower(),
        action="password_reset_confirm_success",
        ip=ip,
        correlation_id=corr_id,
    )

    logger.info("Admin password reset successful")
    return MessageResponse(message="Password has been reset successfully.")
