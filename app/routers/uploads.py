"""File uploads — replaces Firebase Storage."""
from __future__ import annotations

import secrets
import time
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.deps import get_current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Form("misc"),
    user: dict = Depends(get_current_user),
):
    folder = "".join(c for c in folder if c.isalnum() or c in "-_")[:40] or "misc"
    dest_dir = _upload_root() / folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "bin").suffix[:10] or ".bin"
    name = f"{int(time.time() * 1000):x}-{secrets.token_hex(4)}{ext}"
    path = dest_dir / name

    async with aiofiles.open(path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            await out.write(chunk)

    url = f"{settings.API_PUBLIC_URL.rstrip('/')}/uploads/files/{folder}/{name}"
    return {"url": url, "path": f"{folder}/{name}", "name": file.filename}


@router.get("/files/{folder}/{filename}")
async def serve_file(folder: str, filename: str):
    folder = "".join(c for c in folder if c.isalnum() or c in "-_")
    filename = Path(filename).name
    path = _upload_root() / folder / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
