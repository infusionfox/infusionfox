"""
Ensures Alembic migrations and SQLAlchemy models stay in sync.

If a developer adds a column or table to a SQLAlchemy model without
generating a corresponding migration (or vice versa), this test fails.

This catches the most common database drift bug: the model is updated
but no migration is checked in, so the model works in dev/tests
(which run create_all) but breaks in production (which runs Alembic).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.db.models import Base

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def alembic_config():
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


def test_alembic_head_matches_metadata(alembic_config, monkeypatch):
    """Migrating to head should produce a schema that matches Base.metadata.

    Implementation note: ``alembic/env.py`` imports ``DB_URL`` from
    ``app.db.session`` and uses it to override the alembic config URL,
    so just setting ``sqlalchemy.url`` on the config isn't enough — we
    have to make ``app.db.session.DB_URL`` point to our temp file too.

    We do this via ``monkeypatch.setattr`` rather than reloading the
    session module because the module reload reset the cached
    ``SessionLocal`` / ``engine`` objects, which in turn broke any
    subsequent test whose module-level ``from app.db import
    SessionLocal`` had already captured the pre-reload binding. The
    attribute patch is local to this test and auto-rolls-back on exit.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        url = f"sqlite:///{db_path}"

        # Override the DB_URL that alembic/env.py will read when
        # command.upgrade fires. monkeypatch undoes this automatically.
        from app.db import session as session_module

        monkeypatch.setattr(session_module, "DB_URL", url)

        # Apply all migrations
        alembic_config.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_config, "head")

        # Compare the resulting schema to Base.metadata
        engine = create_engine(url)
        with engine.connect() as conn:
            # Exclude FTS5 shadow tables (search_index*) — they are
            # owned by a migration but not by the ORM model. See
            # alembic/env.py for the same filter applied to autogenerate.
            def _skip_fts(name, type_, parent_names):
                return not (
                    type_ == "table"
                    and (name == "search_index" or name.startswith("search_index_"))
                )

            ctx = MigrationContext.configure(conn, opts={"include_name": _skip_fts})
            diff = compare_metadata(ctx, Base.metadata)

        # Filter out trivial diffs that compare_metadata flags as noise
        # (e.g., default values that aren't expressed in DDL on SQLite,
        # type alias differences like VARCHAR vs String).
        meaningful_diff = [
            d
            for d in diff
            if not (
                isinstance(d, tuple) and d and d[0] in ("modify_default", "modify_nullable", "modify_type")
            )
        ]

        assert not meaningful_diff, (
            f"Schema drift detected — Alembic head doesn't match models.\n"
            f"Differences: {meaningful_diff}\n"
            f"Run: alembic revision --autogenerate -m 'describe changes'"
        )
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_alembic_history_is_linear(alembic_config):
    """No branch points in migration history (single linear chain)."""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_config)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected single migration head, found {len(heads)}: {heads}"


def test_alembic_can_downgrade_to_base(alembic_config):
    """Every migration must be reversible (down_revision logic correct)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        url = f"sqlite:///{db_path}"
        alembic_config.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_config, "head")
        # Walk all the way back
        command.downgrade(alembic_config, "base")

        # After full downgrade, no app tables should remain
        # (alembic_version remains, but that's expected)
        engine = create_engine(url)
        from sqlalchemy import inspect

        with engine.connect():
            tables = inspect(engine).get_table_names()
            non_alembic = [t for t in tables if t != "alembic_version"]
            assert not non_alembic, f"Tables remained after full downgrade: {non_alembic}"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
