"""Hyperkalemia emergency hub, workflow page."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/hyperkalemia-emergency", response_class=HTMLResponse)
async def hyperkalemia_emergency_hub(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "hyperkalemia_emergency_hub.html",
        {"request": request},
    )
