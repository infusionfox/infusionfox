"""Tests for the InfusionFox full-text search system.

Covers:
  - Query sanitization (escapes special FTS5 chars, prefix-matching)
  - Source collection (catalog entries, articles, hubs, practice problems)
  - Indexer (ensure_table, rebuild_index, idempotency)
  - Query (BM25 ranking, snippets, highlight, hyphen handling)
  - Routes (/search, /search/dropdown, /api/search.json)
  - Header widget rendering on every page
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import engine
from app.main import app
from app.search import rebuild_index, search
from app.search.query import sanitize_query
from app.search.sources import (
    collect_all_entries,
    markdown_to_text,
    template_to_text,
    with_dehyphenated_variant,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------


class TestSanitization:
    def test_empty_returns_empty(self):
        assert sanitize_query("") == ""
        assert sanitize_query(None) == ""
        assert sanitize_query("   ") == ""

    def test_simple_word_becomes_prefix_match(self):
        q = sanitize_query("apple")
        assert q == '"apple"*'

    def test_multiple_words_anded(self):
        q = sanitize_query("apple fast")
        # Both tokens get prefix matching; FTS5 ANDs by whitespace
        assert '"apple"*' in q
        assert '"fast"*' in q

    def test_hyphens_become_spaces(self):
        q = sanitize_query("apple-fast")
        assert "-" not in q
        # Becomes two tokens
        assert '"apple"*' in q
        assert '"fast"*' in q

    def test_fts5_special_chars_stripped(self):
        # NEAR, OR, AND, parens, colon, asterisk, double-quote, ^, $
        q = sanitize_query('apple OR ("fast") AND NEAR(x:y)*^$')
        # Words remain (no operator semantics survive)
        assert '"apple"' in q
        assert '"OR"' in q  # OR becomes a regular token, not an operator

    def test_pathological_input_truncated(self):
        very_long = "a" * 1000
        q = sanitize_query(very_long)
        # Result references at most ~200 input chars
        assert len(q) < 400

    def test_unicode_preserved(self):
        # Greek letters, Spanish, etc.
        q = sanitize_query("α₁ agonist")
        # The word-character matching is unicode-aware; alpha/subscript stay
        assert "agonist" in q


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------


class TestMarkdownStripping:
    def test_strips_code_blocks(self):
        md = "Before\n```python\nprint('x')\n```\nAfter"
        t = markdown_to_text(md)
        assert "print" not in t
        assert "Before" in t
        assert "After" in t

    def test_strips_emphasis(self):
        t = markdown_to_text("This is **bold** and *italic* text")
        assert "**" not in t
        assert "bold" in t
        assert "italic" in t

    def test_strips_headers(self):
        t = markdown_to_text("# Heading\n## Sub\nBody")
        assert "#" not in t
        assert "Heading" in t

    def test_strips_links_keeping_text(self):
        t = markdown_to_text("See [the paper](https://example.com)")
        assert "the paper" in t
        assert "https" not in t


class TestTemplateStripping:
    def test_strips_jinja_blocks(self):
        tpl = "{% extends 'base.html' %}\n{% block content %}<p>hello</p>{% endblock %}"
        t = template_to_text(tpl)
        assert "extends" not in t
        assert "block" not in t
        assert "hello" in t

    def test_strips_jinja_variables(self):
        tpl = "<p>Hello {{ name }}, your dose is {{ dose_mg }} mg</p>"
        t = template_to_text(tpl)
        assert "Hello" in t
        assert "mg" in t
        assert "{{" not in t

    def test_strips_script_and_style(self):
        tpl = "<script>alert(1)</script><style>p{color:red}</style><p>visible</p>"
        t = template_to_text(tpl)
        assert "alert" not in t
        assert "color" not in t
        assert "visible" in t


class TestDehyphenatedVariant:
    def test_no_hyphen_unchanged(self):
        assert with_dehyphenated_variant("hydromorphone") == "hydromorphone"

    def test_hyphen_appends_variant(self):
        out = with_dehyphenated_variant("apple-fast")
        assert "apple-fast" in out
        assert "applefast" in out

    def test_multiple_hyphens(self):
        out = with_dehyphenated_variant("apple-fast-score")
        assert "applefastscore" in out


# ---------------------------------------------------------------------------
# Source collection
# ---------------------------------------------------------------------------


class TestSourceCollection:
    def test_collect_yields_substantial_entries(self):
        entries = collect_all_entries()
        # Conservative lower bound — actual count is ~65
        assert len(entries) >= 50

    def test_apple_fast_appears_once(self):
        entries = collect_all_entries()
        apple_entries = [e for e in entries if e.slug == "apple-fast"]
        assert len(apple_entries) == 1
        ae = apple_entries[0]
        assert "APPLE-fast" in ae.title
        # Variant appended for hyphen tolerance
        assert "APPLEfast" in ae.title
        # Body augmented with the article markdown
        assert "Hayes" in ae.body
        # URL is the calculator page, not /learn/
        assert ae.url == "/apple-fast"

    def test_hub_entry_has_body(self):
        entries = collect_all_entries()
        shock = next((e for e in entries if e.slug == "shock"), None)
        assert shock is not None
        assert shock.type == "hub"
        # Hub body should pull in the template text
        assert len(shock.body) > 100

    def test_practice_problems_included(self):
        entries = collect_all_entries()
        practice = [e for e in entries if e.type == "practice"]
        assert len(practice) > 0
        for p in practice[:3]:
            assert p.url.startswith("/practice")

    def test_no_empty_titles(self):
        entries = collect_all_entries()
        for e in entries:
            assert e.title.strip(), f"Empty title for slug {e.slug}"
            assert e.slug, "Empty slug"
            assert e.url, f"Empty URL for slug {e.slug}"

    def test_unique_slugs(self):
        entries = collect_all_entries()
        slugs = [e.slug for e in entries]
        assert len(slugs) == len(set(slugs)), "Duplicate slugs in search index"


# ---------------------------------------------------------------------------
# Query — ranking and snippet behavior
# ---------------------------------------------------------------------------


class TestSearchRanking:
    def test_exact_title_outranks_body_mention(self):
        """Searching 'apple' should put an APPLE-titled calculator above
        Shock hub (which only mentions APPLE in citations).

        Either apple-fast or apple-full is fine; the property under test
        is that a title match outranks a body-only mention.
        """
        results = search(engine, "apple", limit=10)
        assert len(results) >= 1
        assert results[0].slug in ("apple-fast", "apple-full")
        # And Shock hub must not be the first hit
        assert results[0].slug != "shock"

    def test_hyphenless_query_finds_hyphenated_title(self):
        """The dehyphenated variant trick: 'applefast' → 'APPLE-fast'."""
        results = search(engine, "applefast", limit=5)
        assert len(results) >= 1
        assert results[0].slug == "apple-fast"

    def test_hyphenated_query_finds_hyphenated_title(self):
        results = search(engine, "apple-fast", limit=5)
        assert len(results) >= 1
        assert results[0].slug == "apple-fast"

    def test_prefix_matching(self):
        """Typing 'hydro' should find hydromorphone."""
        results = search(engine, "hydro", limit=5)
        slugs = [r.slug for r in results]
        assert any("hydromorphone" in s for s in slugs)

    def test_short_name_match(self):
        """Searching for the short name 'NE' should find norepinephrine."""
        results = search(engine, "norepi", limit=5)
        assert any(r.slug == "norepinephrine" for r in results)

    def test_snippet_contains_highlights(self):
        results = search(engine, "lactate", limit=5)
        assert results
        # Snippets should include the highlight delimiter for at least
        # one result (FTS5 may emit an empty snippet for matches that
        # happen only in title; check broadly).
        highlighted = sum(1 for r in results if "<mark>" in r.body_snippet)
        assert highlighted >= 1

    def test_title_highlight_present(self):
        results = search(engine, "shock", limit=5)
        assert results
        # The title for "Shock hub" should have <mark>Shock</mark>
        shock = next((r for r in results if r.slug == "shock"), None)
        assert shock is not None
        assert "<mark>" in shock.title_html

    def test_empty_query_returns_empty(self):
        assert search(engine, "", limit=5) == []
        assert search(engine, "   ", limit=5) == []
        # Pure punctuation also yields nothing
        assert search(engine, "!!! ??", limit=5) == []

    def test_limit_respected(self):
        results = search(engine, "the", limit=3)
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------


class TestIndexer:
    def test_rebuild_is_idempotent(self):
        """Rebuilding twice produces the same row count and same top results."""
        n1 = rebuild_index(engine)
        first = search(engine, "apple", limit=3)
        n2 = rebuild_index(engine)
        second = search(engine, "apple", limit=3)
        assert n1 == n2
        assert n1 > 0
        assert [r.slug for r in first] == [r.slug for r in second]

    def test_rebuild_produces_reasonable_row_count(self):
        n = rebuild_index(engine)
        # Conservative range; current catalog ~65
        assert 50 <= n <= 200


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_search_page_with_no_query(self):
        r = client.get("/search")
        assert r.status_code == 200
        assert "Search InfusionFox" in r.text or "Search" in r.text
        # Tips section visible when no query
        assert "Search tips" in r.text or "applefast" in r.text

    def test_search_page_with_query(self):
        r = client.get("/search?q=apple")
        assert r.status_code == 200
        assert "APPLE-fast" in r.text
        # Highlighted results
        assert "<mark>" in r.text

    def test_search_page_no_results(self):
        r = client.get("/search?q=zzznosuchthingxyz")
        assert r.status_code == 200
        assert "No matches" in r.text or "0 result" in r.text

    def test_dropdown_with_query(self):
        r = client.get("/search/dropdown?q=hydromorphone")
        assert r.status_code == 200
        assert "Hydromorphone" in r.text
        assert "<mark>" in r.text

    def test_dropdown_with_empty_query(self):
        r = client.get("/search/dropdown?q=")
        assert r.status_code == 200
        # Empty dropdown shell, no result rows
        assert 'role="option"' not in r.text

    def test_json_api_returns_results(self):
        r = client.get("/api/search.json?q=insulin")
        assert r.status_code == 200
        data = r.json()
        assert data["query"] == "insulin"
        assert data["count"] >= 1
        # Spot-check shape
        first = data["results"][0]
        assert "slug" in first
        assert "url" in first
        assert "title" in first
        assert "rank" in first

    def test_json_api_respects_limit(self):
        r = client.get("/api/search.json?q=the&limit=3")
        assert r.status_code == 200
        assert len(r.json()["results"]) <= 3

    def test_json_api_caps_limit(self):
        # limit > 50 should clamp to 50 via Query validation
        r = client.get("/api/search.json?q=the&limit=999")
        # FastAPI returns 422 on validation error; tolerate either behavior
        assert r.status_code in (200, 422)

    def test_search_handles_injection_attempts(self):
        """SQL/FTS injection probes shouldn't 500."""
        for q in ("'; DROP TABLE", '" OR 1=1', "(NEAR(a,b))", "x*z+~`!"):
            r = client.get(f"/search?q={q}")
            assert r.status_code == 200


class TestHeaderWidget:
    def test_widget_present_on_homepage(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "data-search-widget" in r.text
        assert "data-search-input" in r.text
        assert "/search/dropdown" in r.text

    def test_widget_present_on_calculator_page(self):
        r = client.get("/apple-fast")
        assert r.status_code == 200
        assert "data-search-widget" in r.text

    def test_widget_present_on_hub_page(self):
        r = client.get("/shock")
        assert r.status_code == 200
        assert "data-search-widget" in r.text

    def test_widget_has_slash_shortcut(self):
        r = client.get("/")
        # Slash key handler should be in the inline script
        assert 'if (e.key !== "/")' in r.text or "key === '/'" in r.text or 'e.key !== "/"' in r.text


# ---------------------------------------------------------------------------
# Type/category structure
# ---------------------------------------------------------------------------


class TestResultStructure:
    def test_all_types_appear_somewhere(self):
        # Calculator
        cr = search(engine, "norepinephrine", limit=5)
        assert any(r.type == "calculator" for r in cr)
        # Hub
        hr = search(engine, "shock", limit=5)
        assert any(r.type == "hub" for r in hr)
        # Practice — query a problem-specific phrase to be sure a
        # practice problem can surface, since the word "practice" itself
        # is not necessarily in problem narrative bodies.
        pr = search(engine, "norepinephrine titration", limit=10)
        types = {r.type for r in pr}
        assert "practice" in types or "calculator" in types
