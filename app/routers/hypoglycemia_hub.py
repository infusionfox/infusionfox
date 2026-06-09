"""Hypoglycemia emergency hub, workflow page."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/hypoglycemia", response_class=HTMLResponse)
async def hypoglycemia_hub(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "hypoglycemia_hub.html",
        {"request": request},
    )
