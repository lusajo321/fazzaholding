"""Auth dependencies."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db, get_doc
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = get_doc(db, "users", payload["sub"])
    if not user or user.get("active") is False:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    return user


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[dict[str, Any]]:
    if not creds or not creds.credentials:
        return None
    payload = decode_token(creds.credentials)
    if not payload or not payload.get("sub"):
        return None
    return get_doc(db, "users", payload["sub"])
