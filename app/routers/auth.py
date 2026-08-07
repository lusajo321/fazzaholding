"""Authentication endpoints — portal SHA-256 password hashes + JWT."""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import InviteToken, get_db, get_doc, list_collection, upsert_doc
from app.deps import get_current_user
from app.security import (
    create_access_token,
    hash_password_bcrypt,
    portal_sha256,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _uid() -> str:
    return f"{int(time.time() * 1000):x}{secrets.token_hex(4)}"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class InviteUseRequest(BaseModel):
    code: str
    name: str
    username: str
    password: str
    avatar: Optional[str] = None


class BootstrapOwnerRequest(BaseModel):
    name: str = "Owner"
    username: str = "owner"
    password: str = Field(min_length=4)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=4)


def _public_user(u: dict[str, Any]) -> dict[str, Any]:
    out = dict(u)
    out.pop("password", None)
    # Keep passwordHash so other devices can verify offline — but strip for token payload safety
    return out


def _find_user(db: Session, username: str) -> Optional[dict[str, Any]]:
    uname = username.lower().strip()
    for u in list_collection(db, "users"):
        if u.get("active") is False:
            continue
        if (u.get("username") or "").lower() == uname or (u.get("name") or "").lower() == uname:
            return u
    return None


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    """Public: whether any users exist (for first-run owner setup)."""
    users = list_collection(db, "users")
    return {"hasUsers": len(users) > 0, "userCount": len(users)}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = _find_user(db, req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored = user.get("passwordHash") or user.get("password_hash") or user.get("password")
    uname = user.get("username") or user.get("name") or req.username
    if not verify_password(req.password, uname, stored):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user["id"], user.get("role") or "Viewer")
    return TokenResponse(access_token=token, user=_public_user(user))


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return _public_user(user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uname = user.get("username") or user.get("name") or ""
    stored = user.get("passwordHash") or user.get("password_hash") or user.get("password")
    if not verify_password(body.old_password, uname, stored):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    user["passwordHash"] = portal_sha256(body.new_password, uname)
    user.pop("password", None)
    user.pop("password_hash", None)
    upsert_doc(db, "users", user["id"], user)
    return {"ok": True}


@router.post("/invite/use", response_model=TokenResponse)
def use_invite(req: InviteUseRequest, db: Session = Depends(get_db)):
    code = req.code.strip().upper()
    token = db.query(InviteToken).filter(InviteToken.code == code).first()
    if not token:
        raise HTTPException(status_code=404, detail="Invite code not found")
    if token.used:
        raise HTTPException(status_code=400, detail="Invite code already used")
    if token.expires_at and token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite code expired")

    username_lower = req.username.lower().strip()
    if _find_user(db, username_lower):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = {
        "id": _uid(),
        "name": req.name,
        "username": username_lower,
        "passwordHash": portal_sha256(req.password, username_lower),
        "role": token.role,
        "avatar": req.avatar,
        "active": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    upsert_doc(db, "users", user["id"], user)

    token.used = True
    token.used_by = user["id"]
    token.used_at = datetime.now(timezone.utc)
    db.commit()

    access = create_access_token(user["id"], user["role"])
    return TokenResponse(access_token=access, user=_public_user(user))


@router.post("/bootstrap-owner", response_model=TokenResponse)
def bootstrap_owner(req: BootstrapOwnerRequest, db: Session = Depends(get_db)):
    """Create the first Owner account when no users exist yet."""
    existing = list_collection(db, "users")
    if existing:
        raise HTTPException(status_code=400, detail="Users already exist — bootstrap disabled")
    username = req.username.lower().strip()
    user = {
        "id": _uid(),
        "name": req.name,
        "username": username,
        "passwordHash": portal_sha256(req.password, username),
        "role": "Owner",
        "active": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    upsert_doc(db, "users", user["id"], user)
    access = create_access_token(user["id"], "Owner")
    return TokenResponse(access_token=access, user=_public_user(user))


@router.post("/invites")
def create_invite(
    role: str = "Team",
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.get("role") not in ("Owner", "Arnold", "IT"):
        raise HTTPException(status_code=403, detail="Not allowed")
    code = secrets.token_hex(3).upper()
    inv = InviteToken(
        id=_uid(),
        code=code,
        role=role,
        created_by=user.get("id"),
    )
    db.add(inv)
    db.commit()
    return {"id": inv.id, "code": code, "role": role}
