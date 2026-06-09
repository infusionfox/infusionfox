"""
Database engine and session management for InfusionFox.

Production uses SQLite on a persistent volume (`/data/infusionfox.db`).
Tests and local dev can override via INFUSIONFOX_DB_URL env var.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def _default_db_url() -> str:
    data_dir_env = os.environ.get("INFUSIONFOX_DATA_DIR")
    if data_dir_env:
        data_dir = Path(data_dir_env)
    else:
        # In Docker, /data is a mounted volume. Locally, fall back to ./data.
        docker_data = Path("/data")
        data_dir = docker_data if docker_data.exists() and os.access(docker_data, os.W_OK) else Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'infusionfox.db').resolve()}"


DB_URL = os.environ.get("INFUSIONFOX_DB_URL") or _default_db_url()

# SQLite needs check_same_thread=False for FastAPI's threadpool model.
# For Postgres this arg is ignored.
_engine_kwargs: dict = {"future": True}
if DB_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    # For in-memory SQLite, every new connection from the default pool
    # gets a brand-new empty database. Use StaticPool so all callers
    # share one connection — this is the standard pattern for ":memory:"
    # SQLite. File-backed SQLite uses the default pool.
    if ":memory:" in DB_URL or "mode=memory" in DB_URL:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DB_URL, **_engine_kwargs)

# Enable WAL mode on SQLite for better concurrency and foreign keys enforcement
if DB_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables for tests and first-boot.

    In production, migrations are managed by Alembic via the container
    entrypoint. This function is therefore a no-op when an
    alembic_version table is already present — calling create_all on an
    Alembic-managed DB would silently leave us without the migration
    history SQL needs to upgrade later.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "alembic_version" in inspector.get_table_names():
        return  # Alembic owns the schema; don't touch it.
    Base.metadata.create_all(bind=engine)
