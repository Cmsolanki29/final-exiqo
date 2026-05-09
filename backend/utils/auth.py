"""JWT, password hashing, and FastAPI security dependencies."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", str(60 * 24 * 7)))  # default 7d
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=True)

# Failed login attempts per normalized email (sliding window)
_failed_attempts: dict[str, list[float]] = defaultdict(list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bcrypt_plaintext(password: str) -> str:
    """
    Bcrypt only uses the first 72 UTF-8 bytes of the password.
    Truncate without splitting a codepoint (raw [:72].decode() can corrupt UTF-8).
    """
    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return password
    cut = 72
    while cut > 0:
        try:
            return raw[:cut].decode("utf-8")
        except UnicodeDecodeError:
            cut -= 1
    return ""


def hash_password(password: str) -> str:
    """Hash a password (bcrypt-safe: at most first 72 UTF-8 bytes)."""
    return pwd_context.hash(_bcrypt_plaintext(password))


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(_bcrypt_plaintext(plain_password), hashed_password)


def _encode(payload: dict[str, Any]) -> str:
    key = SECRET_KEY or "dev-only-change-JWT_SECRET_KEY-in-production"
    return jwt.encode(payload, key, algorithm=ALGORITHM)


def create_access_token(*, user_id: int, email: str | None = None) -> str:
    expire = _utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode: dict[str, Any] = {
        "user_id": user_id,
        "type": "access",
        "exp": expire,
        "iat": _utcnow(),
    }
    if email:
        to_encode["email"] = email
    return _encode(to_encode)


def create_refresh_token(*, user_id: int) -> str:
    expire = _utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode: dict[str, Any] = {
        "user_id": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": _utcnow(),
    }
    return _encode(to_encode)


def decode_token(token: str) -> dict[str, Any]:
    key = SECRET_KEY or "dev-only-change-JWT_SECRET_KEY-in-production"
    try:
        return jwt.decode(token, key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return int(user_id)


def check_login_rate_limit(email: str, max_attempts: int = 5, window_seconds: int = 300) -> None:
    """Raise 429 if too many failed attempts in the sliding window."""
    key = email.strip().lower()
    now = time.time()
    attempts = _failed_attempts[key]
    attempts[:] = [t for t in attempts if now - t < window_seconds]
    if len(attempts) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {max(1, window_seconds // 60)} minutes.",
        )


def record_failed_login(email: str) -> None:
    key = email.strip().lower()
    _failed_attempts[key].append(time.time())


def clear_login_attempts(email: str) -> None:
    _failed_attempts.pop(email.strip().lower(), None)
