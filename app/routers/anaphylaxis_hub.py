"""Anaphylaxis emergency hub, workflow page."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/anaphylaxis", response_class=HTMLResponse)
async def anaphylaxis_hub(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "anaphylaxis_hub.html",
        {"request": request},
    )
