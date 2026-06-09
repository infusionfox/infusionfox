"""add search FTS5 virtual table

Revision ID: c2641fe6cefd
Revises: 4ae1376d9f7c
Create Date: 2026-06-05 17:30:00.000000

Creates a SQLite FTS5 virtual table to back full-text search across
calculators, hubs, learn articles, and practice problems. The table is
populated at application startup (idempotent rebuild) rather than via
ORM writes — content is static and lives in code/files, not in the DB.

Column declaration order matters: the bm25() ranking function in
queries weights indexed columns in declaration order, so reordering
columns here would silently change ranking. Indexed columns first,
UNINDEXED last.

Tokenizer: unicode61 with diacritic removal (handles "résumé" → "resume")
and remove_diacritics 2 (also handles combined characters).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c2641fe6cefd"
down_revision: str | Sequence[str] | None = "4ae1376d9f7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the FTS5 virtual table.

    Indexed columns (BM25 weighted in queries):
      0. title         - primary display name; heaviest weight
      1. short_name    - abbreviation / short label
      2. category      - section bucket (Emergency, Endocrine, etc.)
      3. blurb         - one-line description
      4. body          - full-text body (article markdown, hub content, etc.)

    UNINDEXED columns (stored but not searched):
      - slug, type, url, display_category

    SQLite is the only backend FTS5 is available on; on Postgres this
    migration is a no-op (the search feature gracefully degrades to
    catalog-only matching in app/search/query.py).
    """
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name != "sqlite":
        # FTS5 is SQLite-only. On other backends, skip the table; the
        # search module checks for table presence and falls back.
        return

    op.execute(
        """
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
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    op.execute("DROP TABLE IF EXISTS search_index")
