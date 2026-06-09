"""Heatstroke emergency hub, workflow page for dogs and cats."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/heatstroke", response_class=HTMLResponse)
async def heatstroke_hub(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "heatstroke_hub.html",
        {"request": request},
    )
