"""
Email Sender Service — Brevo REST API

Sends transactional emails (OTP for password reset) via Brevo (formerly Sendinblue).
In development mode (no BREVO_API_KEY), logs the email content instead.
"""

import logging
from typing import Any

import httpx

from app.config import BREVO_API_KEY, EMAIL_FROM, EMAIL_FROM_NAME

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


async def send_otp_email(to_email: str, otp: str) -> bool:
    """
    Send a password reset OTP email via Brevo.

    Returns True on success, False on failure.
    In development mode (no API key), logs the OTP instead.
    """
    if not BREVO_API_KEY:
        logger.warning(
            "BREVO_API_KEY not set — OTP NOT sent via email",
            extra={"to": to_email, "otp": otp, "note": "dev_mode"},
        )
        return True  # Pretend success in dev so the flow can be tested

    payload: dict[str, Any] = {
        "sender": {"name": EMAIL_FROM_NAME, "email": EMAIL_FROM},
        "to": [{"email": to_email}],
        "subject": "ULSS 9 Scaligera — Codice di Verifica per Reset Password",
        "htmlContent": (
            f"<html><body>"
            f"<h2>Reset Password — ULSS 9 Scaligera</h2>"
            f"<p>Il tuo codice di verifica (OTP) è:</p>"
            f"<h1 style='letter-spacing: 8px; font-size: 36px;'>{otp}</h1>"
            f"<p>Questo codice scade tra <strong>10 minuti</strong>.</p>"
            f"<p>Se non hai richiesto il reset della password, ignora questa email.</p>"
            f"<hr><p style='color:#888;font-size:12px;'>"
            f"Azienda ULSS 9 Scaligera — Sistema Amministrativo</p>"
            f"</body></html>"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                BREVO_SEND_URL,
                json=payload,
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            if response.status_code in (200, 201):
                logger.info("OTP email sent", extra={"to": to_email})
                return True
            else:
                logger.error(
                    "Brevo email send failed",
                    extra={"status": response.status_code, "body": response.text[:200]},
                )
                return False
    except Exception as e:
        logger.error("Email send error", extra={"error": str(e)})
        return False
