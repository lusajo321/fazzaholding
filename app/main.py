"""FAZZA FastAPI application — Postgres-backed replacement for Firebase."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import ensure_schema
from app.routers import auth, collections, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="FAZZA Wholesale Jersey Portal — FastAPI + PostgreSQL",
    lifespan=lifespan,
    servers=[{"url": "/api", "description": "Default"}],
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
# Always allow common local origins + file:// (null)
for o in (
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "null",
):
    if o not in origins:
        origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(collections.router)
app.include_router(collections.emp_router)  # /employees, /salary-payments, /employee-loans
app.include_router(uploads.router)


@app.get("/health")
def health():
    return {"status": "healthy", "env": settings.APP_ENV}


@app.get("/api")
def api_root():
    return {
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "docs": "/docs",
        "status": "ok",
    }


# Serve the portal UI from the same origin (avoids CORS when opening via the API)
_INDEX = Path(__file__).resolve().parent.parent / "index.html"
if _INDEX.exists():
    @app.get("/")
    def serve_index():
        return FileResponse(_INDEX)
else:
    @app.get("/")
    def root():
        return {"app": settings.APP_NAME, "status": "ok"}
