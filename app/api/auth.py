"""
Admin auth: login only, no registration.
Single user validated against bcrypt hash; JWT returned for admin API access.
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import (
    ADMIN_PASSWORD_HASH,
    ADMIN_USERNAME,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    JWT_SECRET,
)

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Login with username and password. Returns JWT for admin API."""
    if body.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not _verify_password(body.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = _create_token(body.username)
    return LoginResponse(token=token, username=body.username)


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Dependency: require valid Bearer JWT for admin routes."""
    if not credentials or credentials.credentials is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        username = payload.get("sub")
        if not username or username != ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
