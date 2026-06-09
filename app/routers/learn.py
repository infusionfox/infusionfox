"""Learning module routes.

    /learn                         — index of all modules + practice
                                     problems + future content
    /learn/<slug>                  — if registered as a LearningModule,
                                     render the module page; otherwise
                                     fall through to the clinical-
                                     background article handler

The /learn/<slug> route is registered here BEFORE the content.py
article handler in the router-loading order, so module slugs win
over plain articles. Existing article URLs that don't have a module
fall through to the article handler and keep working.

The /learn index also surfaces the practice-problem section (already
at /learn/practice). Practice and modules are sibling concepts under
the Learn umbrella; the index links to both.
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.learning import all_modules, get_module
from app.practice import PROBLEMS, get_problem

router = APIRouter()


DRUGS_CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content" / "drugs"
MD_EXTENSIONS = ["extra", "sane_lists", "smarty"]


# Markdown does two things badly to our content. First, python-markdown
# doesn't know about YAML front-matter, so the --- delimited block at the
# top of an article gets rendered as a horizontal rule + body text instead
# of being stripped. Second, the markdown processor treats _ as an
# emphasis marker, so anything like _{kg} inside a $$ block gets turned
# into <em>kg</em> and KaTeX never sees a valid math block. The fix is to
# preprocess the source: strip front-matter, then swap $$...$$ blocks for
# placeholder tokens that markdown can't touch, then restore the math
# after markdown is done.
_FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_BLOCK_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$([^\$\n]+?)\$(?!\$)")


def _strip_front_matter(md_text: str) -> str:
    """Remove a leading YAML front-matter block if present."""
    return _FRONT_MATTER_RE.sub("", md_text, count=1)


def _render_markdown(md_path: Path) -> str:
    """Render markdown to HTML, preserving $$math$$ blocks for KaTeX.

    Markdown interprets _ as italic, which destroys LaTeX subscripts in
    $$...$$ blocks. We swap math blocks for placeholders before running
    the markdown processor, then restore them in the output HTML so KaTeX
    auto-render can find clean $$...$$ delimiters in the DOM.
    """
    md_text = _strip_front_matter(md_path.read_text(encoding="utf-8"))

    # Stash both block and inline math behind opaque tokens.
    block_stash: list[str] = []
    inline_stash: list[str] = []

    def _stash_block(m: re.Match[str]) -> str:
        block_stash.append(m.group(0))
        return f"\x00MATHBLOCK{len(block_stash) - 1}\x00"

    def _stash_inline(m: re.Match[str]) -> str:
        inline_stash.append(m.group(0))
        return f"\x00MATHINLINE{len(inline_stash) - 1}\x00"

    md_text = _BLOCK_MATH_RE.sub(_stash_block, md_text)
    md_text = _INLINE_MATH_RE.sub(_stash_inline, md_text)

    html = markdown.markdown(md_text, extensions=MD_EXTENSIONS)

    # Restore math blocks. Block math goes back on its own line so KaTeX
    # renders it in display mode; inline math is restored inline.
    for i, original in enumerate(block_stash):
        html = html.replace(f"\x00MATHBLOCK{i}\x00", original)
    for i, original in enumerate(inline_stash):
        html = html.replace(f"\x00MATHINLINE{i}\x00", original)

    return html


@router.get("/learn", response_class=HTMLResponse)
async def learn_index(request: Request):
    """Top-level Learn index page.

    Lists every registered LearningModule, with a separate section
    pointing to the practice-problem archive. As more module types
    appear (case walkthroughs, video-only CE, etc.), they slot in
    as additional sections here.
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "learn/index.html",
        {
            "request": request,
            "modules": all_modules(),
            "practice_count": len(PROBLEMS),
        },
    )


@router.get("/learn/{slug}", response_class=HTMLResponse)
async def learn_module(slug: str, request: Request):
    """Module page if registered; otherwise let the article handler take it.

    Returns 404 here to allow FastAPI's router stack to fall through
    to the content.py article route, which knows about clinical-
    background articles registered there. If a slug is registered as
    a LearningModule, this route renders the full module page (article
    body + video + calculators + practice + quiz).
    """
    module = get_module(slug)
    if module is None:
        # 404 here so the next-registered /learn/{slug} handler picks
        # it up. Practical note: FastAPI doesn't fall through 404s
        # between handlers on the same path, so this is actually a
        # genuine 404 unless we forward to the content router.
        # See below — we instead handle the fall-through by importing
        # the article-rendering logic.
        return await _render_article_fallback(slug, request)

    # Render the module's article body if it has one
    article_html = ""
    if module.article_slug:
        md_path = DRUGS_CONTENT_DIR / f"{module.article_slug}.md"
        if md_path.exists():
            article_html = _render_markdown(md_path)

    # Hydrate practice problems for the module
    practice_problems = []
    for ps in module.practice_problem_slugs:
        p = get_problem(ps)
        if p is not None:
            practice_problems.append(p)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "learn/module.html",
        {
            "request": request,
            "module": module,
            "article_html": article_html,
            "practice_problems": practice_problems,
        },
    )


async def _render_article_fallback(slug: str, request: Request):
    """Fall through to the content router's article handler.

    Calls the same logic as content.drug_article but inline so the
    URL pattern matches at the registration-order level. This keeps
    /learn/<slug> working for every article slug already in the
    catalog, even when no module is registered.
    """
    from app.routers.content import drug_article

    return await drug_article(slug, request)
