"""
Search query execution for InfusionFox.

Reads from the `search_index` FTS5 virtual table populated by
indexer.rebuild_index(). Uses BM25 column-weighted ranking with custom
weights (title heaviest, body lightest) and prefix matching so partial
typing finds matches as the user types.

User query → safe FTS5 query string:
  - Strip FTS5 special characters that would confuse the parser
  - Tokenize on whitespace
  - Append '*' to each token for prefix matching ("hydro" matches
    "hydromorphone")
  - Implicit AND between tokens (FTS5 default)

The query function returns a list of SearchResult dataclasses with
the highlighted title HTML, snippet HTML, and supporting metadata.
HTML is generated server-side by FTS5's highlight() and snippet()
functions; the templates render it unescaped (it contains only the
<mark> delimiters we requested).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResult:
    slug: str
    type: str  # 'calculator' | 'hub' | 'article' | 'practice'
    title: str  # plain, for fallback contexts
    title_html: str  # title with <mark> highlights — safe to render with |safe
    category: str
    display_category: str
    blurb: str
    body_snippet: str  # FTS5 snippet() output with <mark> highlights
    url: str
    rank: float  # BM25, more-negative = more relevant


# ---------------------------------------------------------------------------
# Query sanitization
# ---------------------------------------------------------------------------


# FTS5 syntax characters and quote chars that could break parsing or
# enable operator injection. We strip everything except letters, digits,
# spaces, and hyphens (hyphens become spaces because the indexer also
# stores a dehyphenated variant of titles, so "apple-fast" and "apple
# fast" and "applefast" all find the APPLE-fast entry).
_SAFE_TOKEN_RE = re.compile(r"[^\w\s-]", flags=re.UNICODE)


def sanitize_query(raw: str | None) -> str:
    """Convert user input into a safe FTS5 MATCH expression.

    Returns an empty string for empty/whitespace-only input so callers
    can short-circuit before hitting the DB.
    """
    if not raw:
        return ""

    # Truncate pathological inputs
    s = raw[:200]

    # Strip dangerous characters; replace hyphens with spaces so they
    # don't anchor as single tokens after sanitation
    s = _SAFE_TOKEN_RE.sub(" ", s)
    s = s.replace("-", " ")

    # Split, drop empties, append prefix-match wildcard to each token
    tokens = [t for t in s.split() if t]
    if not tokens:
        return ""

    # Prefix match per token; FTS5 ANDs them by default
    return " ".join(f'"{t}"*' for t in tokens)


# ---------------------------------------------------------------------------
# Table-availability guard
# ---------------------------------------------------------------------------


def _search_table_available(conn) -> bool:
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type IN ('table','view') AND name = 'search_index' LIMIT 1"
            )
        )
        return result.first() is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main query
# ---------------------------------------------------------------------------


# BM25 column weights (declaration-order from the migration):
#   0. title        — 10.0
#   1. short_name   —  8.0
#   2. category     —  5.0
#   3. blurb        —  3.0
#   4. body         —  1.0
_BM25_WEIGHTS = (10.0, 8.0, 5.0, 3.0, 1.0)

_BM25_CALL = f"bm25(search_index, {', '.join(str(w) for w in _BM25_WEIGHTS)})"

_QUERY_SQL = text(
    f"""
    SELECT
        slug,
        type,
        url,
        category,
        display_category,
        blurb,
        title,
        highlight(search_index, 0, '<mark>', '</mark>') AS title_html,
        snippet(search_index, 4, '<mark>', '</mark>', '…', 24) AS body_snippet,
        {_BM25_CALL} AS rank
    FROM search_index
    WHERE search_index MATCH :q
    ORDER BY rank
    LIMIT :limit
    """
)


def search(engine: Engine, raw_query: str, limit: int = 20) -> list[SearchResult]:
    """Run a search and return ranked results. Empty query → empty list.

    Caller is responsible for trimming `raw_query` if they want — this
    function passes through whitespace handling to `sanitize_query`.
    """
    if engine.dialect.name != "sqlite":
        # Degrade gracefully on non-SQLite: catalog-only fallback could
        # be plugged in here. For now, return empty results.
        return []

    fts_q = sanitize_query(raw_query)
    if not fts_q:
        return []

    limit = max(1, min(int(limit), 100))

    with engine.connect() as conn:
        if not _search_table_available(conn):
            logger.info("Search query received but search_index table missing.")
            return []

        try:
            rows = conn.execute(_QUERY_SQL, {"q": fts_q, "limit": limit}).fetchall()
        except Exception as exc:
            # Defensive: malformed input that slipped through sanitization
            # shouldn't 500 the request. Log and return empty.
            logger.warning("FTS5 query failed (q=%r, fts=%r): %s", raw_query, fts_q, exc)
            return []

    return [
        SearchResult(
            slug=row.slug,
            type=row.type,
            title=_strip_dehyphenated_variant(row.title),
            title_html=_strip_dehyphenated_variant_html(row.title_html),
            category=row.category,
            display_category=row.display_category or row.category,
            blurb=row.blurb or "",
            body_snippet=row.body_snippet or "",
            url=row.url,
            rank=float(row.rank),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Dehyphenated-variant trim
# ---------------------------------------------------------------------------
#
# The indexer stores titles like "APPLE-fast illness severity APPLEfast
# illness severity" (original + dehyphenated). For display we only want
# the original, so we split on the first occurrence of the dehyphenated
# variant marker. Heuristic: the dehyphenated copy is identical to the
# original with hyphens stripped, so we look for the second occurrence
# of any common token.


def _strip_dehyphenated_variant(text_with_variant: str) -> str:
    """Best-effort: return only the original portion of a title.

    If the title doesn't contain a hyphen, no variant was appended.
    Otherwise the indexer appended a dehyphenated copy; we approximate
    "first half" by splitting on length.
    """
    if not text_with_variant or "-" not in text_with_variant:
        # No variant possible
        return text_with_variant
    # The variant is appended after a single space. If we can find the
    # dehyphenated form (original with hyphens removed) as a suffix,
    # strip it. Otherwise return as-is.
    original_guess = text_with_variant
    half = len(text_with_variant) // 2
    # Walk forward from midpoint looking for a single space that
    # separates two halves where the right half is the left half with
    # hyphens removed.
    for i in range(half - 5, half + 6):
        if 0 < i < len(text_with_variant) and text_with_variant[i] == " ":
            left, right = text_with_variant[:i], text_with_variant[i + 1 :]
            if left.replace("-", "") == right:
                return left
    return original_guess


def _strip_dehyphenated_variant_html(html: str) -> str:
    """Same idea but on highlighted HTML. Conservative — only trim when
    the unhighlighted tail unambiguously matches a dehyphenated copy.
    Otherwise return the full string (acceptable: a few highlighted
    duplicates in the result row is preferable to truncating real text).
    """
    if not html or "-" not in html:
        return html
    # Strip <mark> tags for comparison only
    stripped = re.sub(r"</?mark>", "", html)
    plain = _strip_dehyphenated_variant(stripped)
    if plain == stripped:
        return html

    # The original (highlighted) HTML up to the position where the
    # plain text ends. Walking HTML character-by-character with a
    # <mark>-aware counter would be more precise; for now, approximate
    # by truncating to roughly the same length.
    target_chars = len(plain)
    count = 0
    in_tag = False
    for idx, ch in enumerate(html):
        if ch == "<":
            in_tag = True
        elif ch == ">":
            in_tag = False
            continue
        if not in_tag and ch != ">":
            count += 1
        if count >= target_chars and not in_tag:
            return html[: idx + 1]
    return html
