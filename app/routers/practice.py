"""Practice-problem routes for the learning section.

Two routes:
    /learn/practice         — index, problems grouped by topic
    /learn/practice/<slug>  — single problem page with the worked solution

The index page renders every problem inline as a collapsible <details>
block so a learner can scroll through and reveal answers without
navigating. The per-problem page is mostly for sharing — sometimes you
want to send someone a single problem URL.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.practice import PROBLEMS, get_problem, problems_by_topic

router = APIRouter()


@router.get("/learn/practice", response_class=HTMLResponse)
async def practice_index(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "practice/index.html",
        {
            "request": request,
            "problems_by_topic": problems_by_topic(),
            "total_count": len(PROBLEMS),
        },
    )


@router.get("/learn/practice/{slug}", response_class=HTMLResponse)
async def practice_problem(request: Request, slug: str):
    problem = get_problem(slug)
    if problem is None:
        raise HTTPException(status_code=404, detail="Practice problem not found")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "practice/problem.html",
        {"request": request, "problem": problem},
    )
