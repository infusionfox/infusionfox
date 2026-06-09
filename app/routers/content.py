"""Educational content routes.

Articles live as markdown files under content/drugs/<slug>.md.
They're rendered on-demand; a missing article just shows a
placeholder instead of 404-ing, so the calculator is usable
even before editorial content is written.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import markdown
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.calculators import get_drug
from app.calculators.alfaxalone import ALFAXALONE_CATALOG_ENTRY
from app.calculators.blood_gas import BLOOD_GAS_CATALOG_ENTRY
from app.calculators.ca_gluconate import CA_GLUCONATE_CATALOG_ENTRY
from app.calculators.cornell_onco_kl import CORNELL_ONCO_KL_CATALOG_ENTRY
from app.calculators.dopamine_prep import DOPAMINE_PREP_CATALOG_ENTRY
from app.calculators.energy import ENERGY_CATALOG_ENTRY
from app.calculators.fluid_therapy import FLUID_THERAPY_CATALOG_ENTRY
from app.calculators.hydromorphone_cri import HYDROMORPHONE_CRI_CATALOG_ENTRY
from app.calculators.hypernatremia import HYPERNA_CATALOG_ENTRY
from app.calculators.hypokalemia import HYPOKALEMIA_CATALOG_ENTRY
from app.calculators.hypomagnesemia import HYPOMAGNESEMIA_CATALOG_ENTRY
from app.calculators.hypophosphatemia import HYPOPHOSPHATEMIA_CATALOG_ENTRY
from app.calculators.ile import ILE_CATALOG_ENTRY
from app.calculators.insulin_cri_dka import INSULIN_CRI_CATALOG_ENTRY
from app.calculators.insulin_dextrose import INSULIN_DEXTROSE_CATALOG_ENTRY
from app.calculators.insulin_im_dka import INSULIN_IM_CATALOG_ENTRY
from app.calculators.ketamine import KETAMINE_CATALOG_ENTRY
from app.calculators.kitty_magic import KITTY_MAGIC_CATALOG_ENTRY
from app.calculators.lddst import LDDST_CATALOG_ENTRY
from app.calculators.lidocaine import LIDOCAINE_CATALOG_ENTRY
from app.calculators.mannitol import MANNITOL_CATALOG_ENTRY
from app.calculators.methadone import METHADONE_CATALOG_ENTRY
from app.calculators.mlk import MLK_CATALOG_ENTRY
from app.calculators.osmolar_gap import OSMOLAR_GAP_CATALOG_ENTRY
from app.calculators.oxygenation import OXYGENATION_CATALOG_ENTRY
from app.calculators.propofol import PROPOFOL_CATALOG_ENTRY
from app.calculators.tube_feeding import TUBE_FEEDING_CATALOG_ENTRY
from app.routers.addisons_score import ADDISONS_CATALOG_ENTRY
from app.routers.apple_fast import APPLE_FAST_CATALOG_ENTRY
from app.routers.apple_full import APPLE_FULL_CATALOG_ENTRY
from app.routers.blood_gas_stewart import BLOOD_GAS_STEWART_CATALOG_ENTRY
from app.routers.hypothyroid_score import HYPOTHYROID_CATALOG_ENTRY
from app.routers.iris_staging import IRIS_STAGING_CATALOG_ENTRY

router = APIRouter()

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content"
DRUGS_CONTENT_DIR = CONTENT_DIR / "drugs"

MD_EXTENSIONS = ["extra", "sane_lists", "smarty", "toc", "admonition"]


# Custom-route drugs (dopamine, propofol, lidocaine, ketamine, MLK, insulin
# CRI/IM for DKA) aren't in the generic DRUGS catalog used by get_drug(),
# they have their own dedicated routes and catalog-entry dicts. Map their
# slugs here so /learn/<slug> can resolve them too. Each entry must have
# the four fields the article template uses: slug, display_name, category,
# mechanism_summary.
_CUSTOM_ROUTE_CATALOG = {
    entry["slug"]: entry
    for entry in [
        DOPAMINE_PREP_CATALOG_ENTRY,
        PROPOFOL_CATALOG_ENTRY,
        LIDOCAINE_CATALOG_ENTRY,
        KETAMINE_CATALOG_ENTRY,
        MLK_CATALOG_ENTRY,
        KITTY_MAGIC_CATALOG_ENTRY,
        METHADONE_CATALOG_ENTRY,
        HYDROMORPHONE_CRI_CATALOG_ENTRY,
        ALFAXALONE_CATALOG_ENTRY,
        BLOOD_GAS_CATALOG_ENTRY,
        IRIS_STAGING_CATALOG_ENTRY,
        HYPOTHYROID_CATALOG_ENTRY,
        ADDISONS_CATALOG_ENTRY,
        APPLE_FAST_CATALOG_ENTRY,
        APPLE_FULL_CATALOG_ENTRY,
        BLOOD_GAS_STEWART_CATALOG_ENTRY,
        OSMOLAR_GAP_CATALOG_ENTRY,
        OXYGENATION_CATALOG_ENTRY,
        ENERGY_CATALOG_ENTRY,
        HYPERNA_CATALOG_ENTRY,
        HYPOKALEMIA_CATALOG_ENTRY,
        MANNITOL_CATALOG_ENTRY,
        LDDST_CATALOG_ENTRY,
        {
            "slug": "cushings-score",
            "display_name": "Cushing's pretest score",
            "short_name": "Cushing's score",
            "category": "Endocrine & Metabolic",
            "kind": "diagnostic_score",
            "mechanism_summary": (
                "Structured pretest probability score for canine "
                "hyperadrenocorticism. Weights clinical signs and laboratory "
                "findings to triage patients into low / moderate / high "
                "pretest probability before endocrine testing."
            ),
        },
        CORNELL_ONCO_KL_CATALOG_ENTRY,
        INSULIN_CRI_CATALOG_ENTRY,
        INSULIN_IM_CATALOG_ENTRY,
        FLUID_THERAPY_CATALOG_ENTRY,
        HYPOPHOSPHATEMIA_CATALOG_ENTRY,
        HYPOMAGNESEMIA_CATALOG_ENTRY,
        CA_GLUCONATE_CATALOG_ENTRY,
        ILE_CATALOG_ENTRY,
        INSULIN_DEXTROSE_CATALOG_ENTRY,
        TUBE_FEEDING_CATALOG_ENTRY,
        {
            "slug": "transfusion",
            "display_name": "Transfusion",
            "short_name": "Transfusion",
            "category": "Hematology & Transfusion",
            "kind": "calculator",
            "mechanism_summary": (
                "Volume, rate, and reaction management for pRBC, whole "
                "blood, and FFP transfusions in dogs and cats."
            ),
        },
    ]
}


def _render_markdown(md_path: Path) -> str:
    """Render markdown to HTML, preserving $$math$$ blocks for KaTeX.

    Markdown interprets _ as italic, which destroys LaTeX subscripts in
    $$...$$ blocks. We swap math blocks for placeholders before running
    the markdown processor, then restore them in the output HTML so KaTeX
    auto-render can find clean $$...$$ delimiters in the DOM. We also
    strip any leading YAML front-matter block (---\\nkey: val\\n---\\n),
    which stock python-markdown doesn't recognize.
    """
    md_text = md_path.read_text(encoding="utf-8")

    # Strip YAML front-matter block at the top, if present.
    md_text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md_text, count=1, flags=re.DOTALL)

    # Stash math blocks behind opaque tokens so markdown can't eat them.
    block_stash: list[str] = []
    inline_stash: list[str] = []

    def _stash_block(m: re.Match[str]) -> str:
        block_stash.append(m.group(0))
        return f"\x00MATHBLOCK{len(block_stash) - 1}\x00"

    def _stash_inline(m: re.Match[str]) -> str:
        inline_stash.append(m.group(0))
        return f"\x00MATHINLINE{len(inline_stash) - 1}\x00"

    md_text = re.sub(r"\$\$(.+?)\$\$", _stash_block, md_text, flags=re.DOTALL)
    md_text = re.sub(r"(?<!\$)\$([^\$\n]+?)\$(?!\$)", _stash_inline, md_text)

    html = markdown.markdown(md_text, extensions=MD_EXTENSIONS)

    for i, original in enumerate(block_stash):
        html = html.replace(f"\x00MATHBLOCK{i}\x00", original)
    for i, original in enumerate(inline_stash):
        html = html.replace(f"\x00MATHINLINE{i}\x00", original)

    return html


# Some calculator slugs share a clinical-background article with another
# calculator. The page header (drug display_name, category) still comes from
# the slug-specific catalog entry; only the article body is shared. This
# avoids duplicating long-form content that's identical across calculator
# variants.
ARTICLE_SLUG_ALIASES = {
    # Dopamine has two calculators (Plumb's 6×kg method and standard CRI).
    # Pharmacology, indications, monitoring, and clinical context are
    # identical; only the prep recipe differs and that lives on each
    # calculator page. Both /learn/dopamine and /learn/dopamine-cri serve
    # the same dopamine.md article.
    "dopamine-cri": "dopamine",
}


# Article slugs whose calculator URL doesn't follow the default
# slug-from-href derivation in _resolve_calc_url. Add an entry here
# when the catalog entry's slug ("energy-requirements") differs from
# the route path ("/energy"). Keeps the resolver simple at the cost
# of one explicit override per mismatch.
_CALC_URL_OVERRIDES = {
    "energy-requirements": "/energy",
    # MLK calculator was retired in Phase 3 of the analgesia builder.
    # /mlk now redirects to /analgesia-cri with combined-bag mode and
    # the MLK protocol preselected. The mlk learn article still
    # resolves to a calculator — this redirect target.
    "mlk": "/analgesia-cri?prep_mode=combined_bag&opioid=morphine&adjuncts=ketamine,lidocaine",
}


def _calc_url_index() -> dict[str, str]:
    """Build a slug → calculator-URL map from the nav.

    nav_index() is the single source of truth for "where does each
    calculator live" — it drives the home sidebar and the catalog
    pages. Deriving the article-page "Open calculator" link from nav
    avoids drift between the sidebar URL and the article-button URL.

    Slug derivation from href:
      /<slug>               -> <slug>     (every calculator route)
      /<slug>/<rest>        -> <slug>     (tools/* etc.)
    """
    from app.nav import nav_index

    index: dict[str, str] = {}
    for _section, entries in nav_index().items():
        for entry in entries:
            href = entry.href
            slug = href.lstrip("/").split("/", 1)[0]
            if slug:
                # First write wins; nav order is stable so this is
                # deterministic. The duplicate-slug case shouldn't
                # arise in practice — each calculator owns one route.
                index.setdefault(slug, href)
    return index


def _resolve_calc_url(article_slug: str) -> str | None:
    """Return the live calculator URL for an article slug.

    Resolution order:
      1. Explicit override in _CALC_URL_OVERRIDES.
      2. nav_index() lookup by slug (covers every routed calculator).
      3. None if the article has no backing calculator route.
    """
    if article_slug in _CALC_URL_OVERRIDES:
        return _CALC_URL_OVERRIDES[article_slug]
    return _calc_url_index().get(article_slug)


def _resolve_drug_for_article(slug: str):
    """Return a drug-like object with the fields article.html needs.

    Tries the generic DRUGS catalog first (NE, Epi, Dobut, Fent), then
    falls back to the custom-route catalog (dopamine, propofol, lidocaine,
    ketamine, MLK, insulin CRI/IM). Returns None if neither has the slug.
    """
    drug = get_drug(slug)
    if drug is not None:
        return drug
    entry = _CUSTOM_ROUTE_CATALOG.get(slug)
    if entry is not None:
        return SimpleNamespace(**entry)
    return None


@router.get("/learn/{slug}", response_class=HTMLResponse)
async def drug_article(slug: str, request: Request):
    drug = _resolve_drug_for_article(slug)
    if drug is None:
        raise HTTPException(404, f"Unknown drug '{slug}'")

    # If this slug shares an article with another calculator, look up the
    # markdown file under the canonical slug. The drug header above is still
    # the slug-specific one, so the page reads as if the article belongs to
    # this calculator.
    article_slug = ARTICLE_SLUG_ALIASES.get(slug, slug)
    md_path = DRUGS_CONTENT_DIR / f"{article_slug}.md"
    if md_path.exists():
        html_body = _render_markdown(md_path)
        placeholder = False
    else:
        html_body = ""
        placeholder = True

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "article.html",
        {
            "request": request,
            "drug": drug,
            "body_html": html_body,
            "placeholder": placeholder,
            "calc_url": _resolve_calc_url(slug),
        },
    )
