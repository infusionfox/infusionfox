"""
Content source enumeration for the full-text search index.

This module walks the four content surfaces that should be searchable:

  1. Nav catalog entries (calculators, hubs, scoring tools, utilities).
     Source of truth: app/nav.py + app/routers/content.py custom-route catalog.
  2. Learn articles in content/drugs/*.md.
     Source of truth: filesystem markdown.
  3. Hub templates in app/templates/*_hub.html.
     Source of truth: Jinja2 templates; body extracted by stripping
     template control blocks and HTML tags.
  4. Practice problems in app/practice.py.
     Source of truth: PROBLEMS tuple.

Entries are merged where they describe the same destination — a
calculator catalog entry and its companion /learn/<slug> article are
combined into a single SearchEntry whose body concatenates both. This
gives one result row per destination rather than duplicate rows.

Each yielded SearchEntry is one row in the FTS index.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchEntry:
    """One row in the FTS index.

    `category` is the FTS-indexed bucket name (heavy weight in BM25 so
    searches like "endocrine" surface every endocrine tool).
    `display_category` is the UI grouping label shown in results;
    usually identical to `category` but kept separate so we can adjust
    presentation without re-indexing.
    """

    slug: str
    type: str  # 'calculator' | 'hub' | 'article' | 'practice' | 'tool'
    title: str
    short_name: str
    category: str
    blurb: str
    body: str
    url: str
    display_category: str


# ---------------------------------------------------------------------------
# Markdown → plain text
# ---------------------------------------------------------------------------


_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_BOLD_UNDERSCORE_RE = re.compile(r"__([^_]+)__")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!_)_([^_]+)_(?!_)")
_HEADER_RE = re.compile(r"^#{1,6}\s+", flags=re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s*", flags=re.MULTILINE)
_LIST_MARKER_RE = re.compile(r"^\s*[-*+]\s+", flags=re.MULTILINE)
_NUMBERED_LIST_RE = re.compile(r"^\s*\d+\.\s+", flags=re.MULTILINE)
_HORIZONTAL_RULE_RE = re.compile(r"^---+$", flags=re.MULTILINE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_WS_RE = re.compile(r"\s+")


def markdown_to_text(md: str) -> str:
    """Strip markdown syntax for indexing. Lossy but adequate for search."""
    s = md
    s = _CODE_BLOCK_RE.sub(" ", s)
    s = _INLINE_CODE_RE.sub(" ", s)
    s = _IMAGE_RE.sub(" ", s)
    s = _LINK_RE.sub(r"\1", s)
    s = _BOLD_RE.sub(r"\1", s)
    s = _ITALIC_RE.sub(r"\1", s)
    s = _BOLD_UNDERSCORE_RE.sub(r"\1", s)
    s = _ITALIC_UNDERSCORE_RE.sub(r"\1", s)
    s = _HEADER_RE.sub("", s)
    s = _BLOCKQUOTE_RE.sub("", s)
    s = _LIST_MARKER_RE.sub("", s)
    s = _NUMBERED_LIST_RE.sub("", s)
    s = _HORIZONTAL_RULE_RE.sub(" ", s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = _MULTI_WS_RE.sub(" ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Jinja2 + HTML → plain text (for hub templates)
# ---------------------------------------------------------------------------


_JINJA_TAG_RE = re.compile(r"\{%[\s\S]*?%\}")
_JINJA_VAR_RE = re.compile(r"\{\{[\s\S]*?\}\}")
_JINJA_COMMENT_RE = re.compile(r"\{#[\s\S]*?#\}")
_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE)


def template_to_text(html: str) -> str:
    """Best-effort plain-text extraction from a Jinja2 + HTML template."""
    s = html
    s = _JINJA_COMMENT_RE.sub(" ", s)
    s = _JINJA_TAG_RE.sub(" ", s)
    s = _JINJA_VAR_RE.sub(" ", s)
    s = _SCRIPT_RE.sub(" ", s)
    s = _STYLE_RE.sub(" ", s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = _MULTI_WS_RE.sub(" ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Hyphen normalization
# ---------------------------------------------------------------------------


def with_dehyphenated_variant(text: str) -> str:
    """Append a dehyphenated copy of the text so 'applefast' finds 'apple-fast'.

    unicode61 tokenizer splits on hyphen. Indexing both variants lets
    either form (with or without hyphen) match.
    """
    if "-" not in text:
        return text
    dehyphenated = text.replace("-", "")
    if dehyphenated == text:
        return text
    return f"{text} {dehyphenated}"


# ---------------------------------------------------------------------------
# Source 1: nav catalog entries (calculators, hubs, scoring tools, utilities)
# ---------------------------------------------------------------------------


CONTENT_ROOT = Path(__file__).resolve().parent.parent.parent / "content"
TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"
DRUGS_CONTENT_DIR = CONTENT_ROOT / "drugs"


def _read_article_body(slug: str) -> str:
    """Return stripped markdown body for /learn/<slug>, or '' if missing."""
    path = DRUGS_CONTENT_DIR / f"{slug}.md"
    if not path.exists():
        return ""
    try:
        return markdown_to_text(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def _read_hub_body(href: str) -> str:
    """For hub-kind entries, read the corresponding hub template body.

    Hub templates live in `app/templates/*_hub.html`. The naming pattern
    is `<topic>_hub.html` where <topic> is derived from the href
    (e.g. /shock → shock_hub.html, /dka → dka_hub.html). Returns '' when
    no matching template exists.
    """
    slug = href.strip("/")
    candidates = [
        TEMPLATES_ROOT / f"{slug}_hub.html",
        TEMPLATES_ROOT / f"{slug.replace('-', '_')}_hub.html",
    ]
    for path in candidates:
        if path.exists():
            try:
                return template_to_text(path.read_text(encoding="utf-8"))
            except OSError:
                continue
    return ""


def _calculator_url_from_nav(href: str) -> str:
    """Catalog href → canonical calculator URL. Most are already canonical."""
    return href


def iter_nav_entries() -> Iterator[SearchEntry]:
    """Yield one SearchEntry per nav catalog NavEntry.

    Bodies are augmented with article markdown (if a matching
    /learn/<slug>.md exists) and hub template content (if a matching
    *_hub.html exists). This produces one searchable result per
    destination rather than three rows for the same calculator.
    """
    from app.nav import ONE_OFF_CALCULATORS

    for category, entries in ONE_OFF_CALCULATORS.items():
        for nav in entries:
            slug = nav.href.lstrip("/")
            if not slug:
                continue

            body_parts: list[str] = []
            if nav.description:
                body_parts.append(nav.description)

            # Look for companion article body
            article_body = _read_article_body(slug)
            if article_body:
                body_parts.append(article_body)

            # Look for hub template body
            hub_body = _read_hub_body(nav.href)
            if hub_body:
                body_parts.append(hub_body)

            entry_type = "hub" if nav.kind == "hub" else "calculator"
            blurb = nav.catalog_blurb or nav.description or ""

            yield SearchEntry(
                slug=slug,
                type=entry_type,
                title=with_dehyphenated_variant(nav.title),
                short_name=with_dehyphenated_variant(nav.short or ""),
                category=category,
                blurb=blurb,
                body=" ".join(body_parts),
                url=_calculator_url_from_nav(nav.href),
                display_category=category,
            )


# ---------------------------------------------------------------------------
# Source 2: drug-by-category catalog (Plumb-style drug pages)
# ---------------------------------------------------------------------------


def iter_drug_catalog() -> Iterator[SearchEntry]:
    """Yield SearchEntry per drug in the YAML/hardcoded drug catalog.

    Drug pages live at /<slug>. These overlap with some nav entries
    (e.g. propofol, hydromorphone-cri) — duplicates are de-duplicated
    by slug in the indexer.
    """
    from app.calculators import drugs_by_category

    by_category = drugs_by_category()
    for category, drugs in by_category.items():
        for drug in drugs:
            slug = getattr(drug, "slug", "") or ""
            if not slug:
                continue
            title = getattr(drug, "display_name", "") or getattr(drug, "short_name", "") or slug
            short = getattr(drug, "short_name", "") or ""
            blurb = (
                getattr(drug, "catalog_blurb", "")
                or getattr(drug, "mechanism_summary", "")
                or getattr(drug, "indications_summary", "")
                or ""
            )

            # Article body if available
            article_body = _read_article_body(slug)

            # Augment body with the drug's mechanism and indications text
            # so a search for "α₁ agonist" finds norepinephrine even
            # without an article file.
            extra_body_parts: list[str] = []
            for attr in ("mechanism_summary", "indications_summary", "dilution_note"):
                v = getattr(drug, attr, "")
                if v:
                    extra_body_parts.append(v)
            body = " ".join(filter(None, [article_body, *extra_body_parts]))

            yield SearchEntry(
                slug=slug,
                type="calculator",
                title=with_dehyphenated_variant(title),
                short_name=with_dehyphenated_variant(short),
                category=category,
                blurb=blurb,
                body=body,
                url=f"/{slug}",
                display_category=category,
            )


# ---------------------------------------------------------------------------
# Source 3: orphan articles (markdown files without a nav/catalog entry)
# ---------------------------------------------------------------------------


def iter_orphan_articles(known_slugs: set[str]) -> Iterator[SearchEntry]:
    """Yield SearchEntries for /learn/<slug>.md files not covered above.

    Some articles exist purely as explanatory background without a
    backing calculator route (the test suite already documents two:
    ketamine and vasopressor-cri-surgery). They should still be
    searchable; URL points at /learn/<slug>.
    """
    if not DRUGS_CONTENT_DIR.exists():
        return
    for md_path in sorted(DRUGS_CONTENT_DIR.glob("*.md")):
        slug = md_path.stem
        if slug in known_slugs:
            continue
        try:
            body = markdown_to_text(md_path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not body:
            continue
        # Title from first non-blank line if it looks like a heading,
        # otherwise the slug humanized.
        first_lines = [line for line in body.split(" ") if line.strip()][:6]
        title_seed = " ".join(first_lines) if first_lines else slug
        title = title_seed[:80].strip()
        yield SearchEntry(
            slug=slug,
            type="article",
            title=with_dehyphenated_variant(title or slug),
            short_name="",
            category="Reference",
            blurb=body[:200],
            body=body,
            url=f"/learn/{slug}",
            display_category="Reference",
        )


# ---------------------------------------------------------------------------
# Source 4: practice problems
# ---------------------------------------------------------------------------


def iter_practice_problems() -> Iterator[SearchEntry]:
    """Yield one SearchEntry per practice problem.

    All problems live under /practice; the slug encodes the problem
    number so links can target anchors if the practice page supports
    them. Body combines problem narrative + solution steps text.
    """
    try:
        from app.practice import PROBLEMS
    except ImportError:
        return

    for idx, problem in enumerate(PROBLEMS, start=1):
        title = getattr(problem, "title", "") or f"Practice problem {idx}"
        scenario = getattr(problem, "scenario", "") or getattr(problem, "narrative", "")
        topic = getattr(problem, "topic", "Practice")
        difficulty = getattr(problem, "difficulty", "")

        # Solution step text — best-effort across possible attribute shapes
        solution_steps = getattr(problem, "solution_steps", None) or getattr(problem, "steps", ())
        step_text_parts: list[str] = []
        for step in solution_steps or ():
            narrative = getattr(step, "narrative", "")
            if narrative:
                step_text_parts.append(narrative)

        body = " ".join(filter(None, [scenario, *step_text_parts]))

        yield SearchEntry(
            slug=f"practice-{idx}",
            type="practice",
            title=title,
            short_name=f"P{idx}",
            category="Practice",
            blurb=(scenario or topic)[:200],
            body=body,
            url=f"/practice#problem-{idx}",
            display_category=f"Practice · {topic}" + (f" · {difficulty}" if difficulty else ""),
        )


# ---------------------------------------------------------------------------
# Aggregate entry point
# ---------------------------------------------------------------------------


def collect_all_entries() -> list[SearchEntry]:
    """Aggregate every searchable entry, de-duplicating by slug.

    Order of precedence (earlier sources win on slug collision):
      1. Nav entries — most metadata-rich, hand-curated
      2. Drug catalog — overlaps with nav for some drugs
      3. Orphan articles — fills gaps
      4. Practice problems — never collide with the above (different slug shape)
    """
    seen_slugs: set[str] = set()
    out: list[SearchEntry] = []

    for entry in iter_nav_entries():
        if entry.slug in seen_slugs:
            continue
        seen_slugs.add(entry.slug)
        out.append(entry)

    for entry in iter_drug_catalog():
        if entry.slug in seen_slugs:
            continue
        seen_slugs.add(entry.slug)
        out.append(entry)

    for entry in iter_orphan_articles(seen_slugs):
        if entry.slug in seen_slugs:
            continue
        seen_slugs.add(entry.slug)
        out.append(entry)

    for entry in iter_practice_problems():
        # Practice slugs are unique by construction (practice-N)
        out.append(entry)

    return out
