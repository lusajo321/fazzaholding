"""Firestore-compatible document CRUD over Postgres JSONB."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import (
    ALLOWED_COLLECTIONS,
    delete_doc,
    get_db,
    get_doc,
    list_collection,
    upsert_doc,
)
from app.deps import get_current_user

router = APIRouter(tags=["collections"])


class UpsertBody(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class BatchOp(BaseModel):
    op: str  # set | delete
    coll: str
    id: str
    data: Optional[dict[str, Any]] = None


class BatchBody(BaseModel):
    ops: list[BatchOp]


def _check_coll(coll: str) -> None:
    if coll not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown collection: {coll}")


@router.get("/collections")
def list_known_collections(user: dict = Depends(get_current_user)):
    return sorted(ALLOWED_COLLECTIONS)


@router.get("/collections/{coll}")
def get_all(coll: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _check_coll(coll)
    return list_collection(db, coll)


@router.get("/collections/{coll}/{doc_id}")
def get_one(
    coll: str,
    doc_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _check_coll(coll)
    doc = get_doc(db, coll, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


@router.put("/collections/{coll}/{doc_id}")
def put_one(
    coll: str,
    doc_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Upsert a full document (Firestore setDoc merge semantics for whole object)."""
    _check_coll(coll)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    # Allow wrapping as {"data": {...}} or raw document
    payload = body.get("data") if "data" in body and len(body) == 1 and isinstance(body.get("data"), dict) else body
    return upsert_doc(db, coll, doc_id, payload)


@router.delete("/collections/{coll}/{doc_id}")
def remove_one(
    coll: str,
    doc_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _check_coll(coll)
    ok = delete_doc(db, coll, doc_id)
    return {"ok": ok}


@router.post("/collections/batch")
def batch_write(
    body: BatchBody,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    results = []
    for op in body.ops:
        _check_coll(op.coll)
        if op.op == "delete":
            results.append({"coll": op.coll, "id": op.id, "ok": delete_doc(db, op.coll, op.id)})
        elif op.op in ("set", "upsert", "write"):
            if not op.data:
                raise HTTPException(status_code=400, detail=f"Missing data for {op.coll}/{op.id}")
            doc = upsert_doc(db, op.coll, op.id, op.data)
            results.append({"coll": op.coll, "id": op.id, "ok": True, "doc": doc})
        else:
            raise HTTPException(status_code=400, detail=f"Unknown op: {op.op}")
    return {"results": results}


@router.get("/sync")
def sync_all(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Bulk pull — one round-trip for syncDownAll."""
    out: dict[str, list] = {}
    for coll in sorted(ALLOWED_COLLECTIONS):
        out[coll] = list_collection(db, coll)
    return out


# ── Employee REST aliases (frontend _empFetch paths) ──────────────────────

emp_router = APIRouter(tags=["employees"])


@emp_router.get("/employees")
def emp_list_employees(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_collection(db, "employees")


@emp_router.get("/salary-payments")
def emp_list_salary(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_collection(db, "salaryPayments")


@emp_router.get("/employee-loans")
def emp_list_loans(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return list_collection(db, "employeeLoans")


@emp_router.get("/employees/{doc_id}")
def emp_get_employee(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    doc = get_doc(db, "employees", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


@emp_router.get("/salary-payments/{doc_id}")
def emp_get_salary(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    doc = get_doc(db, "salaryPayments", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


@emp_router.get("/employee-loans/{doc_id}")
def emp_get_loan(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    doc = get_doc(db, "employeeLoans", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


@emp_router.post("/employees")
def emp_create_employee(body: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    import secrets, time
    doc_id = body.get("id") or f"{int(time.time() * 1000):x}{secrets.token_hex(4)}"
    body = dict(body); body["id"] = doc_id
    return upsert_doc(db, "employees", doc_id, body)


@emp_router.post("/salary-payments")
def emp_create_salary(body: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    import secrets, time
    doc_id = body.get("id") or f"{int(time.time() * 1000):x}{secrets.token_hex(4)}"
    body = dict(body); body["id"] = doc_id
    return upsert_doc(db, "salaryPayments", doc_id, body)


@emp_router.post("/employee-loans")
def emp_create_loan(body: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    import secrets, time
    doc_id = body.get("id") or f"{int(time.time() * 1000):x}{secrets.token_hex(4)}"
    body = dict(body); body["id"] = doc_id
    return upsert_doc(db, "employeeLoans", doc_id, body)


@emp_router.patch("/employees/{doc_id}")
def emp_patch_employee(doc_id: str, body: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    existing = get_doc(db, "employees", doc_id) or {"id": doc_id}
    existing.update(body); existing["id"] = doc_id
    return upsert_doc(db, "employees", doc_id, existing)


@emp_router.patch("/salary-payments/{doc_id}")
def emp_patch_salary(doc_id: str, body: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    existing = get_doc(db, "salaryPayments", doc_id) or {"id": doc_id}
    existing.update(body); existing["id"] = doc_id
    return upsert_doc(db, "salaryPayments", doc_id, existing)


@emp_router.patch("/employee-loans/{doc_id}")
def emp_patch_loan(doc_id: str, body: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    existing = get_doc(db, "employeeLoans", doc_id) or {"id": doc_id}
    existing.update(body); existing["id"] = doc_id
    return upsert_doc(db, "employeeLoans", doc_id, existing)


@emp_router.delete("/employees/{doc_id}")
def emp_del_employee(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return {"ok": delete_doc(db, "employees", doc_id)}


@emp_router.delete("/salary-payments/{doc_id}")
def emp_del_salary(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return {"ok": delete_doc(db, "salaryPayments", doc_id)}


@emp_router.delete("/employee-loans/{doc_id}")
def emp_del_loan(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return {"ok": delete_doc(db, "employeeLoans", doc_id)}
