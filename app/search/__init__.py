"""InfusionFox full-text search package."""

from app.search.indexer import ensure_table, rebuild_index
from app.search.query import SearchResult, sanitize_query, search

__all__ = [
    "SearchResult",
    "ensure_table",
    "rebuild_index",
    "sanitize_query",
    "search",
]
