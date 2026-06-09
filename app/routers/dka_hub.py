"""DKA management hub, workflow page tying together the DKA calculators."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/dka", response_class=HTMLResponse)
async def dka_hub_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dka_hub.html",
        {"request": request},
    )
