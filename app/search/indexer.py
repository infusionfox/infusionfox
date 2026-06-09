"""
FTS5 index builder for InfusionFox search.

The index lives in the same SQLite database as the rest of the app
state (currently just feedback). It's a `search_index` virtual table
created by Alembic migration c2641fe6cefd; this module owns its
population.

Indexing strategy: rebuild from scratch on every app startup. Content
is static (files + code) and the table is tiny (~100-150 rows for the
current catalog), so a full rebuild costs <1 second and avoids the
complexity of incremental indexing. The DDL is also issued
idempotently (CREATE VIRTUAL TABLE IF NOT EXISTS) so test databases
that haven't run the Alembic migration still get the table.

For non-SQLite backends, the rebuild is a no-op — the search module
falls back to catalog-only filtering. InfusionFox ships on SQLite, so
this is defensive only.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.search.sources import SearchEntry, collect_all_entries

logger = logging.getLogger(__name__)


# Mirror of the Alembic migration DDL. Kept here so test DBs (which
# bypass Alembic via init_db) can still create the table.
_CREATE_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    title,
    short_name,
    category,
    blurb,
    body,
    slug UNINDEXED,
    type UNINDEXED,
    url UNINDEXED,
    display_category UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
)
"""


_INSERT_SQL = text(
    """
    INSERT INTO search_index (
        title, short_name, category, blurb, body,
        slug, type, url, display_category
    ) VALUES (
        :title, :short_name, :category, :blurb, :body,
        :slug, :type, :url, :display_category
    )
    """
)


def _is_sqlite(engine: Engine) -> bool:
    return engine.dialect.name == "sqlite"


def _table_exists(conn: Any) -> bool:
    """Probe for the search_index virtual table.

    Uses sqlite_master rather than inspector.get_table_names() because
    SQLAlchemy's inspector may not see FTS5 virtual tables.
    """
    try:
        result = conn.execute(
            text("SELECT name FROM sqlite_master " "WHERE type IN ('table','view') AND name = 'search_index'")
        )
        return result.first() is not None
    except Exception:
        return False


def ensure_table(engine: Engine) -> bool:
    """Create the FTS table if it doesn't exist. Return True if available.

    No-op on non-SQLite backends; the caller's degraded fallback path
    takes over.
    """
    if not _is_sqlite(engine):
        return False

    with engine.begin() as conn:
        if _table_exists(conn):
            return True
        try:
            conn.execute(text(_CREATE_TABLE_SQL))
            return True
        except Exception as exc:
            logger.warning("Could not create search_index table: %s", exc)
            return False


def _entry_to_params(entry: SearchEntry) -> dict[str, str]:
    """Coerce a SearchEntry to the parameter dict the INSERT expects."""
    return {
        "title": entry.title or "",
        "short_name": entry.short_name or "",
        "category": entry.category or "",
        "blurb": entry.blurb or "",
        "body": entry.body or "",
        "slug": entry.slug or "",
        "type": entry.type or "",
        "url": entry.url or "",
        "display_category": entry.display_category or entry.category or "",
    }


def rebuild_index(engine: Engine) -> int:
    """Drop and repopulate the FTS index. Returns the row count written.

    The DELETE is preferred over DROP+CREATE because re-creating the
    virtual table on every startup churns the underlying FTS shadow
    tables. DELETE FROM on an FTS5 table is fast at this scale.

    No-op (returns 0) on non-SQLite backends.
    """
    if not _is_sqlite(engine):
        logger.info("Search indexer: non-SQLite backend, skipping rebuild.")
        return 0

    if not ensure_table(engine):
        return 0

    entries = collect_all_entries()

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM search_index"))
        for entry in entries:
            conn.execute(_INSERT_SQL, _entry_to_params(entry))

    logger.info("Search indexer: rebuilt with %d entries.", len(entries))
    return len(entries)
