"""
Admin auth: login via email + password from database.
JWT returned for admin API access. Password can be reset via email.
"""

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from app.core.audit import log_login
from app.core.database import get_db
from app.core.models import AdminUser
from app.core.utils import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str | None = Field(None, min_length=1, max_length=255)
    username: str | None = Field(None, min_length=1, max_length=100)  # legacy, treated as email
    password: str = Field(min_length=1, max_length=200)

    def get_email(self) -> str:
        """Resolve email from either email or username field."""
        e = (self.email or self.username or "").strip().lower()
        if not e:
            raise ValueError("Email or username is required")
        return e


class LoginResponse(BaseModel):
    token: str
    email: str
    username: str


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_token(username: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request):
    """Login with email and password. Returns JWT for admin API."""
    ip = get_client_ip(request)
    corr_id = getattr(request.state, "correlation_id", None)
    try:
        email = body.get_email()
    except ValueError:
        raise HTTPException(status_code=422, detail="Email or username is required")

    async with get_db() as db:
        result = await db.execute(
            select(AdminUser).where(AdminUser.email == email, AdminUser.is_active == True)
        )
        user = result.scalars().first()

    if not user:
        log_login(email, ip, success=False, correlation_id=corr_id)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not _verify_password(body.password, user.password_hash):
        log_login(email, ip, success=False, correlation_id=corr_id)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    log_login(email, ip, success=True, correlation_id=corr_id)
    token = _create_token(email)
    display = user.display_name or email.split("@")[0]
    return LoginResponse(token=token, email=email, username=display)


@router.get("/me")
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Return current admin user info from JWT. Requires Bearer token."""
    if not credentials or credentials.credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization")
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        async with get_db() as db:
            result = await db.execute(
                select(AdminUser).where(AdminUser.email == email, AdminUser.is_active == True)
            )
            user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return {"email": user.email, "username": user.display_name or user.email.split("@")[0]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Dependency: require valid Bearer JWT for admin routes. Returns email."""
    if not credentials or credentials.credentials is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
