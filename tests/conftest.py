"""
Shared pytest fixtures for the InfusionFox test suite.

Conventions:
- Each calculator gets its own test file in tests/calculators/
- Boundary tests cover threshold values from cited sources
- Species tests confirm dog vs cat differences are encoded correctly
- Hard-ceiling tests confirm safety limits cannot be exceeded
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `app` importable from tests
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use an in-memory SQLite for tests so the file-system DB is never touched.
os.environ.setdefault("INFUSIONFOX_DB_URL", "sqlite:///:memory:")


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_tables():
    """Create all SQLAlchemy tables once at session start.

    The FastAPI TestClient runs the app's lifespan only when used inside
    a ``with`` context manager. Most tests use module-level
    ``client = TestClient(app)`` without the context manager, which
    skips lifespan — and therefore skips ``init_db()``. That's fine for
    tests that only hit calculator routes (no DB writes), but tests
    that write to the database (feedback, disclaimer, admin) need the
    tables to exist before the first request fires.

    Calling ``init_db()`` here is idempotent (skips if alembic_version
    is present) and safe to repeat. The in-memory SQLite uses
    StaticPool so all sessions and the engine share one connection;
    the table created here is visible to subsequent test code.
    """
    from app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="session")
def jinja_env():
    """Jinja environment for template render tests, no Flask context."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(ROOT / "app" / "templates"),
        autoescape=True,
    )
    env.globals["site_name"] = "InfusionFox"
    env.globals["tagline"] = "Cited. Calculated. Confirmed."
    env.globals["css_version"] = "test"
    env.globals["drug_nav"] = lambda: {}
    return env


@pytest.fixture(scope="session")
def fastapi_client():
    """TestClient against the live app — for integration tests only."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _build_search_index():
    """Populate the FTS search index once per test session.

    The TestClient created by tests is bare (no context-manager
    lifespan), so the application's startup `rebuild_index` doesn't
    run. Build it here so search-dependent tests find content.

    Safe even when the rest of the suite doesn't touch search — the
    rebuild is fast (~200ms) and the FTS table is private to the
    in-memory DB.
    """
    from app.db.session import engine
    from app.search import rebuild_index

    rebuild_index(engine)
    yield
