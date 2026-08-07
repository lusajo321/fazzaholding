#!/usr/bin/env python3
"""Bootstrap the first Owner account and optionally import firebase-export.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path

# Allow running as `python scripts/bootstrap_owner.py` from repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, ensure_schema, list_collection, upsert_doc  # noqa: E402


def portal_sha256(password: str, username: str) -> str:
    salt = "fazza-portal-v1::" + (username or "").lower()
    return hashlib.sha256(f"{salt}::{password}".encode()).hexdigest()


def uid() -> str:
    return f"{int(time.time() * 1000):x}{secrets.token_hex(4)}"


def bootstrap(name: str, username: str, password: str) -> dict:
    ensure_schema()
    db = SessionLocal()
    try:
        existing = list_collection(db, "users")
        if existing:
            print(f"Users already exist ({len(existing)}). Skipping create.")
            return existing[0]
        username = username.lower().strip()
        user = {
            "id": uid(),
            "name": name,
            "username": username,
            "passwordHash": portal_sha256(password, username),
            "role": "Owner",
            "active": True,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        upsert_doc(db, "users", user["id"], user)
        print(f"Created Owner: {username} / (password you set)")
        return user
    finally:
        db.close()


def import_export(path: Path) -> None:
    ensure_schema()
    data = json.loads(path.read_text())
    db = SessionLocal()
    try:
        for coll, items in data.items():
            if coll.startswith("_") or not isinstance(items, list):
                continue
            n = 0
            for item in items:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                upsert_doc(db, coll, item["id"], item)
                n += 1
            print(f"  {coll}: {n}")
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="Arnold Lyimo")
    p.add_argument("--username", default="arnold")
    p.add_argument("--password", default="admin123")
    p.add_argument("--import-json", type=Path, default=None, help="Optional firebase-export.json")
    args = p.parse_args()

    print("── Bootstrap owner ──")
    bootstrap(args.name, args.username, args.password)

    if args.import_json and args.import_json.exists():
        print("── Import", args.import_json, "──")
        import_export(args.import_json)
        print("Done.")
    elif args.import_json:
        print("Import file not found:", args.import_json)


if __name__ == "__main__":
    main()
