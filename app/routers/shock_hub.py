"""Shock decision support hub — workflow page for differentiating and treating shock in dogs and cats."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/shock", response_class=HTMLResponse)
async def shock_hub(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "shock_hub.html",
        {"request": request},
    )
