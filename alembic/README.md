# Migrations workflow (Alembic)

Laravel analogy: `alembic revision --autogenerate` ≈ `make:migration`,
`alembic upgrade head` ≈ `migrate`.

## Important: what Alembic tracks here

Only tables backed by real SQLAlchemy models in `app/database.py` (currently
just `InviteToken` → `invite_tokens`) are tracked. The ~30 JSONB "document"
tables (`sales`, `orders`, `customers`, ...) are created/altered at runtime
via raw SQL and are deliberately excluded from autogenerate (see
`include_object` in `alembic/env.py`) so it can never propose dropping them.
If you want Alembic to manage one of those tables going forward, declare it
as a proper model on `Base` first.

## Local / desktop workflow (after changing a model)

```bash
source venv/bin/activate

# 1. Edit/add a model in app/database.py (or wherever models live)

# 2. Generate a migration from the diff
alembic revision --autogenerate -m "add foo column to invite_tokens"

# 3. Open the generated file in alembic/versions/ and review it —
#    autogenerate is a helper, not gospel. Fix names/defaults as needed.

# 4. Apply it to your local DB
alembic upgrade head

# 5. Commit the migration file along with your model change
git add alembic/versions/xxxx_add_foo_column.py app/database.py
git commit -m "add foo column to invite_tokens"
```

Other useful commands:

```bash
alembic current      # what revision is the DB currently at
alembic history       # list all migrations
alembic check          # does the DB match the models right now? (no changes made)
alembic downgrade -1   # undo the last migration
```

## VPS workflow (after `git pull`)

**First time only** — the VPS database already has the current schema
(it predates Alembic), so do NOT run `upgrade head` for the baseline
migration or Alembic will try to (re)apply it. Instead, stamp the DB as
already being at that revision:

```bash
cd /path/to/fazza-api
source venv/bin/activate
pip install -r requirements.txt   # picks up alembic
alembic stamp head                 # marks current baseline as applied, no DDL runs
```

**Every deploy after that**, once the baseline is stamped, just run real
migrations normally:

```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

If a deploy ever fails partway through a migration, `alembic current` tells
you exactly which revision the DB is on so you know where you stand.

## Credentials

`alembic.ini` has no database URL in it (`sqlalchemy.url =` is intentionally
blank). `alembic/env.py` sets it at runtime from `app.config.settings.DATABASE_URL`,
which comes from `.env` (gitignored) — same source your app already uses.
Nothing sensitive is in a committed file.
