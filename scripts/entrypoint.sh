#!/bin/sh
# InfusionFox container entrypoint.
#
# Handles four DB states before starting the app:
#
#   1. Brand-new (no tables): alembic creates schema from baseline.
#   2. Alembic-managed at a known revision: alembic upgrades to head.
#   3. Legacy boot (schema present, no alembic_version): stamp at head.
#   4. Pinned to a revision alembic doesn't know about — happens after a
#      destructive schema change like the auth-removal sweep where the
#      old baseline migration was deleted and a new one written. We
#      drop the legacy auth/billing tables (which no longer have model
#      definitions), preserve any feedback rows, clear alembic_version,
#      and let the new baseline run from scratch.
#
# Idempotent. Containers can be restarted any number of times.

set -e

cd /app

# Inspect the DB to figure out which of the four states we're in.
# Exits with:
#   0 — alembic upgrade will handle it
#   2 — legacy DB needs `alembic stamp head` then upgrade
#   3 — DB pinned to an unknown revision; needs the auth-removal sweep
set +e
INSPECT_OUTPUT=$(python3 - <<'PY'
import sys
from sqlalchemy import inspect, text
from app.db.session import engine

inspector = inspect(engine)
tables = set(inspector.get_table_names())

if not tables:
    print("[entrypoint] Empty database, alembic will create the schema.")
    sys.exit(0)

if "alembic_version" not in tables:
    print("[entrypoint] Legacy DB (schema present, no alembic_version).")
    print("[entrypoint] Stamping at HEAD so new migrations apply cleanly.")
    sys.exit(2)

# alembic_version exists — is the recorded revision one we still know about?
# Compare against the migration scripts directory.
from pathlib import Path
import re

with engine.connect() as conn:
    row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    current_rev = row[0] if row else None

if not current_rev:
    print("[entrypoint] alembic_version table is empty, alembic upgrade will populate.")
    sys.exit(0)

versions_dir = Path("/app/alembic/versions")
known_revs = set()
for f in versions_dir.glob("*.py"):
    text_content = f.read_text()
    m = re.search(r'^revision[: ]+[^=]*=\s*[\'"]([0-9a-f]+)[\'"]', text_content, re.MULTILINE)
    if m:
        known_revs.add(m.group(1))

if current_rev in known_revs:
    print(f"[entrypoint] Alembic-managed DB at known revision {current_rev}, will upgrade.")
    sys.exit(0)

print(f"[entrypoint] DB pinned to unknown revision {current_rev!r}.")
print("[entrypoint] This happens after a destructive schema change where the")
print("[entrypoint] old baseline migration was deleted. Will drop legacy")
print("[entrypoint] auth/billing tables, clear alembic_version, and let the")
print("[entrypoint] new baseline run.")
sys.exit(3)
PY
)
RC=$?
set -e
printf "%s\n" "$INSPECT_OUTPUT"

if [ "$RC" = "2" ]; then
    alembic stamp head

elif [ "$RC" = "3" ]; then
    # Destructive recovery path: drop everything except `feedback`, clear
    # alembic_version, then let alembic upgrade re-apply the new baseline.
    # The feedback table itself is preserved across the sweep so existing
    # user feedback rows survive.
    python3 - <<'PY'
from sqlalchemy import text
from app.db.session import engine

LEGACY_TABLES = [
    "audit_log",
    "ce_records",
    "entitlements",
    "purchases",
    "subscriptions",
    "products",
    "magic_link_tokens",
    "sessions",
    "users",
]

with engine.begin() as conn:
    # SQLite respects PRAGMA foreign_keys per-connection.
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    for t in LEGACY_TABLES:
        conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
    conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    print("[entrypoint] Legacy tables dropped; alembic_version cleared.")
PY
    # Now alembic_version is gone but feedback still exists. We need
    # alembic to stamp at the new baseline rather than re-create the
    # feedback table (which would fail). Stamp first, then upgrade
    # (which becomes a no-op since stamp already moved us to head).
    alembic stamp head

elif [ "$RC" != "0" ]; then
    echo "[entrypoint] DB inspection failed (rc=$RC), aborting." >&2
    exit "$RC"
fi

echo "[entrypoint] Running alembic upgrade head..."
alembic upgrade head

echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
