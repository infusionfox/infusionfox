"""
Tests for the /learn/<module-slug> module pages.

Each module page should render:
- Objectives
- Video (if module has one)
- Background (the article body with KaTeX-bracketed math intact)
- Quiz (the post-test)
- Apply the math (Calculators)
- Practice problems

Section ORDER matters — quiz must come right after the article so the
reader is tested on the material while it's still fresh. See STATUS.md
and learn/module.html.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.learning import all_modules
from app.main import app

client = TestClient(app)


class TestModuleIndex:
    """The /learn index lists all modules."""

    def test_learn_index_loads(self):
        r = client.get("/learn")
        assert r.status_code == 200

    def test_learn_index_lists_all_modules(self):
        r = client.get("/learn")
        assert r.status_code == 200
        for module in all_modules():
            assert module.title in r.text, f"Module '{module.title}' missing from /learn index"


class TestModulePageRenders:
    """Each module's detail page should render without error."""

    def test_every_module_page_returns_200(self):
        for module in all_modules():
            r = client.get(f"/learn/{module.slug}")
            assert r.status_code == 200, f"/learn/{module.slug} returned {r.status_code}"

    def test_every_module_page_includes_its_title(self):
        for module in all_modules():
            r = client.get(f"/learn/{module.slug}")
            assert module.title in r.text


class TestModulePageStructure:
    """The vasopressor module is the canonical example — all sections
    present. If a future module omits a section, the slug-specific
    assertion will catch it; the structure tests below catch regressions
    in the template itself."""

    MODULE_SLUG = "vasopressor-cri-surgery"

    def test_objectives_section_present(self):
        r = client.get(f"/learn/{self.MODULE_SLUG}")
        assert 'id="objectives"' in r.text

    def test_article_section_present(self):
        r = client.get(f"/learn/{self.MODULE_SLUG}")
        assert 'id="article"' in r.text

    def test_quiz_section_present(self):
        r = client.get(f"/learn/{self.MODULE_SLUG}")
        assert 'id="quiz"' in r.text

    def test_calculators_section_present(self):
        r = client.get(f"/learn/{self.MODULE_SLUG}")
        assert 'id="calculators"' in r.text

    def test_practice_section_present(self):
        r = client.get(f"/learn/{self.MODULE_SLUG}")
        assert 'id="practice"' in r.text


class TestModuleSectionOrdering:
    """Quiz must come right after the article (Background) so the reader is
    tested while the material is still fresh. Order matters; locking this
    in protects against future template edits that scramble it.

    Expected order: objectives → video → article → quiz → calculators →
    practice."""

    def test_quiz_comes_after_article(self):
        r = client.get("/learn/vasopressor-cri-surgery")
        article_pos = r.text.find('id="article"')
        quiz_pos = r.text.find('id="quiz"')
        assert article_pos > 0 and quiz_pos > 0
        assert article_pos < quiz_pos, "Quiz should come after article (Background) — see STATUS.md"

    def test_quiz_comes_before_calculators(self):
        r = client.get("/learn/vasopressor-cri-surgery")
        quiz_pos = r.text.find('id="quiz"')
        calc_pos = r.text.find('id="calculators"')
        assert quiz_pos > 0 and calc_pos > 0
        assert quiz_pos < calc_pos

    def test_calculators_comes_before_practice(self):
        r = client.get("/learn/vasopressor-cri-surgery")
        calc_pos = r.text.find('id="calculators"')
        practice_pos = r.text.find('id="practice"')
        assert calc_pos > 0 and practice_pos > 0
        assert calc_pos < practice_pos

    def test_full_section_order(self):
        r = client.get("/learn/vasopressor-cri-surgery")
        positions = {
            section: r.text.find(f'id="{section}"')
            for section in ("objectives", "article", "quiz", "calculators", "practice")
        }
        for section, pos in positions.items():
            assert pos > 0, f"section {section} not found"
        # Strictly increasing order
        sorted_positions = sorted(positions.items(), key=lambda kv: kv[1])
        assert [s for s, _ in sorted_positions] == [
            "objectives",
            "article",
            "quiz",
            "calculators",
            "practice",
        ]


class TestModuleNavOrdering:
    """The jump-link nav at the top of the module page should match the
    section order in the body."""

    def test_nav_order_matches_section_order(self):
        r = client.get("/learn/vasopressor-cri-surgery")
        # There are multiple <nav> elements on the page (site nav, module
        # nav). The module's tab nav has class="calc-tabs". Isolate that
        # one before checking href order.
        calc_pos = r.text.find('class="calc-tabs"')
        assert calc_pos > 0, "module calc-tabs nav not found"
        end_pos = r.text.find("</nav>", calc_pos)
        assert end_pos > calc_pos
        nav_section = r.text[calc_pos:end_pos]
        positions = {
            target: nav_section.find(f'href="#{target}"')
            for target in ("objectives", "article", "quiz", "calculators", "practice")
        }
        for target, pos in positions.items():
            assert pos > 0, f"nav link to #{target} missing"
        sorted_positions = sorted(positions.items(), key=lambda kv: kv[1])
        assert [t for t, _ in sorted_positions] == [
            "objectives",
            "article",
            "quiz",
            "calculators",
            "practice",
        ]


# ---------------------------------------------------------------------------
# Article pages — /learn/<drug-slug> rendered by app/routers/content.py.
# Distinct from the module pages above; lives in the same file because
# both share the /learn/ URL prefix and a future contributor will look
# here first when chasing a learn-page regression.
# ---------------------------------------------------------------------------


import re  # noqa: E402

from app.calculators import DRUGS  # noqa: E402
from app.routers.content import _CUSTOM_ROUTE_CATALOG  # noqa: E402


def _article_slugs():
    """Every catalog slug that has a /learn/<slug> article page."""
    slugs = {entry["slug"] for entry in _CUSTOM_ROUTE_CATALOG.values()}
    slugs.update(d.slug for d in DRUGS)
    return sorted(slugs)


class TestArticleOpenCalculatorLink:
    """Every article page has an 'Open calculator →' button at the top.
    The link must point at a route that actually returns 200. This was
    silently broken for ~11 calculators because article.html hardcoded
    /{slug}, which only works for engine-driven CRIs; bespoke
    calculators with custom routes (blood gas, LDDST, hypernatremia,
    iris-staging, etc.) 404'd from their own clinical background page.
    The resolver in app/routers/content.py now derives the URL from
    nav_index() with a small override map for slug-vs-route mismatches.
    """

    _BUTTON_RE = re.compile(r'<a href="([^"]+)" class="btn">Open calculator')

    def test_every_article_has_a_working_calc_link(self):
        """Every article that renders an Open-calculator button must
        link to a route that returns 200. Some articles intentionally
        omit the button — e.g. ketamine, which appears in the practice
        problems and as an ingredient in MLK / Kitty Magic, but is not
        a standalone calculator surface per the project owner. Those
        articles render without the button (the template guards on
        `{% if calc_url %}`); the test allows that case and only fails
        when a rendered button points at a broken route.
        """
        bad = []
        for slug in _article_slugs():
            r = client.get(f"/learn/{slug}")
            assert r.status_code == 200, f"/learn/{slug} returned {r.status_code}"
            m = self._BUTTON_RE.search(r.text)
            if not m:
                # Button intentionally omitted; that's a valid state.
                continue
            calc_url = m.group(1)
            r2 = client.get(calc_url, follow_redirects=False)
            if r2.status_code != 200:
                bad.append((slug, f"{calc_url} -> {r2.status_code}"))
        assert not bad, "broken Open-calculator links on article pages:\n  " + "\n  ".join(
            f"{s}: {why}" for s, why in bad
        )

    def test_ketamine_article_links_to_ketamine_route(self):
        """Tim re-decided in 2026-06: ketamine now has a standalone
        /ketamine surface (the existing two-indication-mode calculator
        was preserved and surfaced in nav). The learn article must
        therefore render an Open-calculator button pointing at it. The
        opposite was previously asserted (session 13) — that test was
        intentionally inverted when the calculator was surfaced.
        """
        r = client.get("/learn/ketamine")
        assert r.status_code == 200
        m = self._BUTTON_RE.search(r.text)
        assert m is not None, "ketamine article must render an Open-calculator button"
        assert m.group(1) == "/ketamine", (
            f"ketamine article must link to /ketamine, got {m.group(1)!r}"
        )

    def test_blood_gas_article_links_to_blood_gas_route(self):
        """Specific pin: the original bug Tim reported."""
        r = client.get("/learn/blood-gas")
        assert r.status_code == 200
        m = self._BUTTON_RE.search(r.text)
        assert m is not None, "Open-calculator button missing on /learn/blood-gas"
        assert m.group(1) == "/blood-gas", f"blood gas article must link to /blood-gas, got {m.group(1)!r}"

    def test_energy_article_links_to_energy_route_despite_slug_mismatch(self):
        """Specific pin: the /learn/energy-requirements article must
        link to /energy (the calculator's actual route), not to
        /energy-requirements (which doesn't exist) or /energy-requirements
        (which also doesn't exist). This catches future regressions in
        _CALC_URL_OVERRIDES."""
        r = client.get("/learn/energy-requirements")
        assert r.status_code == 200
        m = self._BUTTON_RE.search(r.text)
        assert m is not None
        assert m.group(1) == "/energy", f"energy article must link to /energy, got {m.group(1)!r}"


# ---------------------------------------------------------------------------
# File-driven article coverage. The class above iterates over the catalog
# (DRUGS + _CUSTOM_ROUTE_CATALOG); this one iterates over the *.md files on
# disk. The two views catch different bug classes:
#
#   - Catalog-driven: an entry registered with a slug that 404s at /learn/.
#   - File-driven:    an article file added without a catalog entry
#                     (so /learn/<slug> 404s and the catalog-driven loop
#                     never even sees it).
#
# Articles that exist intentionally without a backing calculator route
# (general explanatory pieces, not tied to a single tool) are listed in
# EXPLANATORY_NO_CALC. Anything else must resolve to a calculator URL.
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from app.routers.content import _resolve_calc_url  # noqa: E402

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "drugs"


def _article_files():
    """Every *.md in content/drugs/, sorted for stable test IDs."""
    return sorted(CONTENT_DIR.glob("*.md"))


# Articles deliberately not backed by a single calculator route. These render
# at /learn/<slug> as background reading but their Open-calculator button is
# intentionally suppressed (the article template guards on `{% if calc_url %}`).
# Add a slug here only when the article is genuinely an overview, not when
# the calculator route is missing.
EXPLANATORY_NO_CALC = {
    # Vasopressor & inotrope prep math across multiple calculators —
    # this article walks the bag-prep arithmetic for norepi / dopamine /
    # dobutamine together rather than belonging to any single calculator.
    "vasopressor-cri-surgery",
}


class TestArticleFileCoverage:
    """Iterate over the *.md files in content/drugs/ rather than over the
    catalog. Catches an article added to disk that nobody wired into the
    catalog or that has a slug-vs-route mismatch the override map should
    cover."""

    @pytest.mark.parametrize(
        "article_path",
        _article_files(),
        ids=lambda p: p.stem,
    )
    def test_article_file_renders_at_learn_slug(self, article_path):
        """Every *.md in content/drugs/ must be reachable at /learn/<stem>.

        Failure means the article exists on disk but isn't wired into
        _CUSTOM_ROUTE_CATALOG (or, for engine drugs, into DRUGS). Fix by
        registering the slug in app/routers/content.py.
        """
        slug = article_path.stem
        r = client.get(f"/learn/{slug}")
        assert r.status_code == 200, (
            f"/learn/{slug} returned {r.status_code}. The file "
            f"content/drugs/{slug}.md exists but isn't registered in "
            f"_CUSTOM_ROUTE_CATALOG (or DRUGS for engine drugs)."
        )

    @pytest.mark.parametrize(
        "article_path",
        _article_files(),
        ids=lambda p: p.stem,
    )
    def test_article_file_resolves_to_calculator_url(self, article_path):
        """Every *.md must resolve to a calculator URL, unless explicitly
        listed in EXPLANATORY_NO_CALC.

        Failure modes this catches:
          - Article added with a slug that doesn't match its calculator's
            route (e.g. energy-requirements → /energy), without a matching
            entry in _CALC_URL_OVERRIDES.
          - Calculator route renamed without updating the override map.
        """
        slug = article_path.stem
        if slug in EXPLANATORY_NO_CALC:
            pytest.skip(
                f"{slug} is an explanatory article without a backing " f"calculator route (deliberate)."
            )
        url = _resolve_calc_url(slug)
        assert url is not None, (
            f"Article {slug}.md has no resolvable calculator URL. "
            f"Either add a _CALC_URL_OVERRIDES entry in "
            f"app/routers/content.py mapping {slug!r} to its route, or "
            f"if this is an explanatory-only article, add it to "
            f"EXPLANATORY_NO_CALC in this test."
        )
