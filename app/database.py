"""Database access over the restored Firestore→Postgres tables.

Each collection maps to a real table (orders, users, …). Rows are returned as
JSON documents so the frontend can keep its existing document API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import Json as _PgJson
from sqlalchemy import Boolean, Column, DateTime, String, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

COLLECTION_TABLES: dict[str, str] = {
    "sales": "sales",
    "customers": "customers",
    "batches": "batches",
    "orders": "orders",
    "payments": "payments",
    "transfers": "transfers",
    "warehouses": "warehouses",
    "stock": "stock",
    "credits": "credits",
    "creditPayments": "creditPayments",
    "cargo": "cargo",
    "cargoPayments": "cargoPayments",
    "cashLogs": "cashLogs",
    "bankDeposits": "bankDeposits",
    "bankWithdrawals": "bankWithdrawals",
    "jerseyLibrary": "jerseyLibrary",
    "receivedLog": "receivedLog",
    "salesTeam": "salesTeam",
    "commissions": "commissions",
    "commissionPayouts": "commissionPayouts",
    "expenses": "expenses",
    "users": "users",
    "settings": "settings",
    "tombstones": "tombstones",
    "notifications": "notifications",
    "fcmTokens": "fcmTokens",
    "shares": "shares",
    "auditLog": "auditLog",
    "employees": "employees",
    "salaryPayments": "salaryPayments",
    "employeeLoans": "employeeLoans",
}

ALLOWED_COLLECTIONS = frozenset(COLLECTION_TABLES.keys())

_FIELD_MAP = {
    "total_tzs": "totalTZS",
    "total_usd": "totalUSD",
    "total_rmb": "totalRMB",
    "unit_price_rmb": "unitPriceRMB",
    "invoice": "invoiceNo",
    "invoice_no": "invoiceNo",
    "more_details": "moreDetails",
    "batch_id": "batchId",
    "order_id": "orderId",
    "customer_id": "customerId",
    "customer_name": "customer",
    "customer_phone": "customerPhone",
    "supplier_id": "supplierId",
    "warehouse_id": "warehouseId",
    "warehouse_name": "warehouseName",
    "sold_by": "soldById",
    "sold_by_name": "soldBy",
    "logged_by": "loggedBy",
    "logged_by_id": "loggedById",
    "paid_amount": "paidAmount",
    "payment_status": "paymentStatus",
    "payment_method": "paymentMethod",
    "sale_price_tzs": "salePriceTZS",
    "sale_price_usd": "salePriceUSD",
    "total_discount": "totalDiscount",
    "tzs_rate": "tzsRate",
    "rate_at_payment": "rateAtPayment",
    "amount_tzs": "amountTZS",
    "amount_usd": "amountUSD",
    "date_given": "dateGiven",
    "default_sale_price_usd": "defaultSalePriceUSD",
    "default_sale_price_tzs": "defaultSalePriceTZS",
    "img_url": "imgUrl",
    "logo_url": "logoUrl",
    "logo_urls": "logoUrls",
    "transferred_overflow": "transferredOverflow",
    "principal_tzs": "principalTZS",
    "principal_usd": "principalUSD",
    "password_hash": "passwordHash",
    "is_default": "isDefault",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
    "from_warehouse": "fromWarehouseId",
    "to_warehouse": "toWarehouseId",
    "from_name": "fromName",
    "to_name": "toName",
    "transferred_by": "transferredBy",
    "biometric_id": "biometricId",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _snake_to_camel(key: str) -> str:
    if key in _FIELD_MAP:
        return _FIELD_MAP[key]
    if "_" not in key:
        return key
    parts = key.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)


def row_to_doc(mapping: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    for k, v in mapping.items():
        if k in ("extra", "meta", "data") and isinstance(v, dict):
            extras.update(v)
            continue
        if k == "__docId":
            continue
        if v is None:
            continue
        camel = _snake_to_camel(k)
        if camel != k and camel in mapping and mapping[camel] is not None:
            continue
        out[camel if camel != k else k] = v

    for k, v in extras.items():
        if k not in out or out[k] is None:
            out[k] = v

    if not out.get("id"):
        if mapping.get("id"):
            out["id"] = mapping["id"]
        elif mapping.get("__docId"):
            out["id"] = mapping["__docId"]
    return out


def table_exists(db: Session, table: str) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=:t"
        ),
        {"t": table},
    ).first()
    return row is not None


def ensure_table(db: Session, table: str) -> None:
    if table_exists(db, table):
        return
    db.execute(
        text(
            f"CREATE TABLE {_qident(table)} ("
            f"id TEXT PRIMARY KEY, "
            f"extra JSONB DEFAULT '{{}}'::jsonb"
            f")"
        )
    )
    db.commit()


def _table_columns(db: Session, table: str) -> set[str]:
    rows = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t"
        ),
        {"t": table},
    ).fetchall()
    return {r[0] for r in rows}


def _id_column(cols: set[str]) -> str:
    if "id" in cols:
        return "id"
    if "__docId" in cols:
        return "__docId"
    # shares table has only __docId in dump — treat as id
    return "id"


def list_collection(db: Session, coll: str) -> list[dict[str, Any]]:
    table = COLLECTION_TABLES.get(coll)
    if not table:
        return []
    ensure_table(db, table)
    result = db.execute(text(f"SELECT * FROM {_qident(table)}"))
    cols = list(result.keys())
    docs = []
    for row in result.fetchall():
        mapping = dict(zip(cols, row))
        # shares: promote __docId → id
        if not mapping.get("id") and mapping.get("__docId"):
            mapping["id"] = mapping["__docId"]
        doc = row_to_doc(mapping)
        if not doc.get("id"):
            continue
        if coll == "users" and not doc.get("username") and not doc.get("name"):
            continue
        docs.append(doc)
    return docs


def get_doc(db: Session, coll: str, doc_id: str) -> Optional[dict[str, Any]]:
    table = COLLECTION_TABLES.get(coll)
    if not table or not table_exists(db, table):
        return None
    cols = _table_columns(db, table)
    id_col = _id_column(cols)
    result = db.execute(
        text(f"SELECT * FROM {_qident(table)} WHERE {_qident(id_col)} = :id"),
        {"id": doc_id},
    )
    row = result.fetchone()
    if not row and id_col == "id" and "__docId" in cols:
        result = db.execute(
            text(f'SELECT * FROM {_qident(table)} WHERE "__docId" = :id'),
            {"id": doc_id},
        )
        row = result.fetchone()
    if not row:
        return None
    mapping = dict(zip(result.keys(), row))
    if not mapping.get("id") and mapping.get("__docId"):
        mapping["id"] = mapping["__docId"]
    return row_to_doc(mapping)


def upsert_doc(db: Session, coll: str, doc_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    table = COLLECTION_TABLES.get(coll)
    if not table:
        raise ValueError(f"Unknown collection: {coll}")

    clean = dict(payload or {})
    clean["id"] = doc_id
    ensure_table(db, table)
    cols = _table_columns(db, table)
    id_col = _id_column(cols)

    known: dict[str, Any] = {}
    extras: dict[str, Any] = {}
    for k, v in clean.items():
        if k in cols:
            known[k] = v
        else:
            snake = "".join(("_" + c.lower() if c.isupper() else c) for c in k).lstrip("_")
            if snake in cols and snake not in known:
                known[snake] = v
            else:
                extras[k] = v

    if id_col not in known:
        known[id_col] = doc_id
    if "id" in cols:
        known["id"] = doc_id
    if "__docId" in cols:
        known["__docId"] = doc_id
    if "extra" in cols and extras:
        known["extra"] = extras

    # psycopg2 can't adapt a raw dict/list bind param (e.g. stock.baleQtys,
    # receivedLog.items) — wrap it so it's sent as JSON for jsonb columns.
    for k, v in known.items():
        if isinstance(v, (dict, list)):
            known[k] = _PgJson(v)

    col_names = list(known.keys())
    placeholders = [f":{c}" for c in col_names]

    # shares has no PK — delete+insert
    # Resolve primary key via information_schema / pg_catalog (handles camelCase names)
    pk_cols = db.execute(
        text(
            "SELECT kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            "  AND tc.table_schema = 'public' AND tc.table_name = :t"
        ),
        {"t": table},
    ).fetchall()

    if not pk_cols:
        # No primary key (e.g. shares) — delete by __docId/id then insert
        if "id" in cols:
            db.execute(text(f"DELETE FROM {_qident(table)} WHERE id = :id"), {"id": doc_id})
        elif "__docId" in cols:
            db.execute(text(f'DELETE FROM {_qident(table)} WHERE "__docId" = :id'), {"id": doc_id})
        sql = (
            f"INSERT INTO {_qident(table)} ({', '.join(_qident(c) for c in col_names)}) "
            f"VALUES ({', '.join(placeholders)})"
        )
        db.execute(text(sql), known)
    else:
        updates = [f"{_qident(c)} = EXCLUDED.{_qident(c)}" for c in col_names if c != id_col]
        conflict = _qident(id_col)
        sql = (
            f"INSERT INTO {_qident(table)} ({', '.join(_qident(c) for c in col_names)}) "
            f"VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT ({conflict}) DO UPDATE SET "
            f"{', '.join(updates) if updates else f'{conflict} = EXCLUDED.{conflict}'}"
        )
        db.execute(text(sql), known)

    db.commit()
    return clean


def delete_doc(db: Session, coll: str, doc_id: str) -> bool:
    table = COLLECTION_TABLES.get(coll)
    if not table or not table_exists(db, table):
        return False
    cols = _table_columns(db, table)
    if "id" in cols:
        result = db.execute(text(f"DELETE FROM {_qident(table)} WHERE id = :id"), {"id": doc_id})
    elif "__docId" in cols:
        result = db.execute(
            text(f'DELETE FROM {_qident(table)} WHERE "__docId" = :id'), {"id": doc_id}
        )
    else:
        return False
    db.commit()
    return (result.rowcount or 0) > 0


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)


class Base(DeclarativeBase):
    pass


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    id = Column(String, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, nullable=False)
    used = Column(Boolean, default=False)
    used_by = Column(String, nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
