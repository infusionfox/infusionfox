"""
Tests that exercise the Alembic migration history.

These are belt-and-suspenders to the CI `alembic check` step: they run
inside the test process, so a model/migration mismatch surfaces during
local development too, not just on push.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    """Run alembic with INFUSIONFOX_DB_URL pointed at db_path."""
    env = os.environ.copy()
    env["INFUSIONFOX_DB_URL"] = f"sqlite:///{db_path}"
    return subprocess.run(
        ["alembic", *args],
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "alembic-test.db"


class TestUpgradeHead:
    def test_fresh_db_upgrades_to_head_cleanly(self, db_path):
        result = _run_alembic(["upgrade", "head"], db_path)
        assert result.returncode == 0, result.stderr

    def test_alembic_version_table_present(self, db_path):
        _run_alembic(["upgrade", "head"], db_path)
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "alembic_version" in tables


class TestCheckCommand:
    """`alembic check` should report no drift between models and head."""

    def test_no_drift_after_upgrade(self, db_path):
        _run_alembic(["upgrade", "head"], db_path)
        result = _run_alembic(["check"], db_path)
        assert result.returncode == 0, (
            f"alembic check failed — drift between models and migrations:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "No new upgrade operations detected" in result.stdout


class TestSchemaContents:
    """The fully-upgraded schema should contain all expected tables."""

    def test_all_app_tables_present(self, db_path):
        _run_alembic(["upgrade", "head"], db_path)
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()

        # The auth/billing/CE schema was removed when those concerns were
        # outsourced to infrastructure (Cloudflare Zero Trust for the
        # closed beta; a hosted auth provider for paid users later). The
        # domain tables now are `feedback` (user-submitted reports) and
        # `disclaimer_acceptances` (legal audit trail for the hard-block
        # disclaimer modal on the free launch). If you ever see other
        # auth-era tables (users, sessions, magic_link_tokens, products,
        # etc.) appear here, a stale migration has resurrected them.
        expected = {"feedback", "disclaimer_acceptances"}
        missing = expected - tables
        assert not missing, f"Missing tables after migration: {missing}"

        legacy_auth_tables = {
            "users",
            "sessions",
            "magic_link_tokens",
            "subscriptions",
            "purchases",
            "products",
            "entitlements",
            "ce_records",
            "audit_log",
        }
        resurrected = tables & legacy_auth_tables
        assert not resurrected, (
            f"Auth-era tables resurrected by a migration: {resurrected}"
        )
