"""Password hashing (portal SHA-256 + bcrypt) and JWT tokens."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def portal_sha256(password: str, username: str) -> str:
    """Match the frontend hashPassword(): SHA-256 of fazza-portal-v1::{user}::{pass}."""
    salt = "fazza-portal-v1::" + (username or "").lower()
    msg = f"{salt}::{password}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


def hash_password_bcrypt(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, username: str, stored: Optional[str]) -> bool:
    """Accept portal SHA-256 hashes, bcrypt hashes, or legacy plaintext."""
    if not stored:
        return False
    stored = str(stored)
    # Portal SHA-256 (64 hex chars)
    if len(stored) == 64 and all(c in "0123456789abcdef" for c in stored.lower()):
        return portal_sha256(plain, username) == stored.lower()
    # bcrypt
    if stored.startswith("$2"):
        try:
            return pwd_context.verify(plain, stored)
        except Exception:
            return False
    # Legacy plaintext
    return plain == stored


def create_access_token(user_id: str, role: str, extra: Optional[dict[str, Any]] = None) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
