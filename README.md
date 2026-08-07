# FAZZA API — FastAPI + PostgreSQL

Backend for the FAZZA supplier portal. Replaces Firebase with Postgres (`fazza-prod`).

## Quick start

```bash
cd fazza-api
source venv/bin/activate   # or: ./venv/bin/activate
pip install -r requirements.txt

# Create first Owner (default: arnold / admin123)
python scripts/bootstrap_owner.py --username arnold --password 'YOUR_PASSWORD'

# Optional: seed from an old Firebase export
python scripts/bootstrap_owner.py --import-json "/path/to/firebase-export.json"

# Run API + serve index.html
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://127.0.0.1:8000 — the portal is served from the same origin.

API docs: http://127.0.0.1:8000/docs

## Config (`.env`)

| Variable | Meaning |
|----------|---------|
| `DATABASE_URL` | `postgresql://lusajo1:lusajo321@localhost:5432/fazza-prod` |
| `JWT_SECRET` | Long random string |
| `CORS_ORIGINS` | Comma-separated origins |
| `API_PUBLIC_URL` | Public base URL for uploaded file links |

## API shape

- `POST /auth/login` `{username, password}` → JWT + user
- `POST /auth/bootstrap-owner` — first user only
- `GET /sync` — all collections (authenticated)
- `GET/PUT/DELETE /collections/{name}/{id}` — document CRUD
- `POST /collections/batch` — batch writes
- `POST /uploads` — file upload (multipart)
- `/employees`, `/salary-payments`, `/employee-loans` — HR REST aliases

Data is stored as JSONB documents in table `docs (coll, id, data)`.

## Migrating live Firebase data

1. Log into the old Firebase-hosted portal and let it sync.
2. In DevTools console, dump local cache, or use a Firestore export.
3. `PUT` each document into `/collections/{coll}/{id}` (or use `--import-json`).

The frontend still uses `window.__firebase` / `window._apiMod` — those now talk to this API.
