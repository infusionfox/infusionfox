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

# Defensive sweep: keep only the current baseline migration.
#
# Background: this codebase had its alembic history rewritten when the
# auth/billing schema was removed. The old baseline migrations are
# expected to be gone. If, for any reason (Docker layer cache, build
# context, etc.), stale migration files end up in /app/alembic/versions
# alongside the current baseline, alembic refuses to run with a
# "Multiple head revisions" error and the container restart-loops.
#
# This block sweeps anything that isn't the known-good baseline before
# alembic runs. Idempotent — when the directory already contains only
# the baseline, this is a no-op.
#
# To change the pinned baseline: update BASELINE_REV below, then also
# update the auth-removal recovery block further down (look for the
# `alembic stamp head` call) — that one stamps to head, which is fine.
BASELINE_REV="4ae1376d9f7c"
VERSIONS_DIR="/app/alembic/versions"
if [ -d "$VERSIONS_DIR" ]; then
    REMOVED=""
    for f in "$VERSIONS_DIR"/*.py; do
        # The glob keeps the literal pattern when no files match; skip that.
        [ -f "$f" ] || continue
        # Filename is something like "4ae1376d9f7c_baseline_schema_feedback_only.py".
        # Keep the file whose basename starts with the baseline revision.
        case "$(basename "$f")" in
            "${BASELINE_REV}"_*) ;;  # keep
            *)
                REMOVED="$REMOVED $(basename "$f")"
                rm -f "$f"
                ;;
        esac
    done
    # Also wipe the bytecode cache, which can keep stale compiled
    # versions of deleted .py migration files alive across restarts.
    rm -rf "$VERSIONS_DIR/__pycache__"
    if [ -n "$REMOVED" ]; then
        echo "[entrypoint] Swept stale migration files (kept only $BASELINE_REV):$REMOVED"
    fi
fi

# Defensive sweep #2: remove orphaned Python modules and templates.
#
# Same problem as the migration sweep above — if the deploy layered our
# new bundle over an older one rather than replacing the directory
# cleanly, deleted files survive on disk. Those files reference symbols
# that no longer exist (e.g. account_admin.py imports current_user from
# app.auth, which is gone), so they crash on router-discovery import.
#
# We list the deleted paths explicitly rather than trying to be clever.
# When this list is added to (future cleanup removes more files), the
# new entries get appended here. The find for __pycache__ at the end
# catches the matching .pyc files so reimports don't resurrect anything.
ORPHANED_FILES="
app/auth.py
app/email.py
app/routers/auth.py
app/routers/account_admin.py
app/services/disclaimer.py
app/templates/account.html
app/templates/pricing.html
"
ORPHANED_DIRS="
app/templates/auth
app/templates/admin
"
REMOVED_ORPHANS=""
for relpath in $ORPHANED_FILES; do
    if [ -f "/app/$relpath" ]; then
        rm -f "/app/$relpath"
        REMOVED_ORPHANS="$REMOVED_ORPHANS $relpath"
    fi
done
for relpath in $ORPHANED_DIRS; do
    if [ -d "/app/$relpath" ]; then
        rm -rf "/app/$relpath"
        REMOVED_ORPHANS="$REMOVED_ORPHANS $relpath/"
    fi
done
# Sweep all __pycache__ directories under /app/app — cheap, catches any
# stale .pyc whose source .py was just removed. This is safe because
# Python will simply recompile any pyc it needs on the next import.
find /app/app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
if [ -n "$REMOVED_ORPHANS" ]; then
    echo "[entrypoint] Swept orphaned files from a layered deploy:$REMOVED_ORPHANS"
fi

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
    "disclaimer_acceptances",
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
