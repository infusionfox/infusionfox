"""
Router auto-discovery.

Every `.py` file in this package that defines a top-level `router`
attribute (a `fastapi.APIRouter` instance) is automatically registered
with the FastAPI app at startup. To add a new endpoint, drop a new
`.py` file here that exposes `router = APIRouter()` — no edits to
`main.py` required.

Files starting with an underscore (`_helpers.py` etc.) are skipped,
which is the standard Python convention for "internal, not auto-loaded."
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).parent
_PACKAGE_NAME = __name__


def discover_routers() -> Iterator[APIRouter]:
    """Yield every APIRouter found in this package's modules.

    Order matters when routers share path prefixes. FastAPI matches in
    registration order, so dedicated routers (e.g., mlk.py's static
    `/mlk`) must be registered BEFORE catalog dispatchers (e.g.,
    calculators.py's pattern `/{slug}`). Otherwise the pattern matches
    first and the dedicated route is never reached.

    Strategy: alphabetical by default, but specific dispatcher modules
    are always last. Files starting with `_` are skipped.
    """
    # Modules whose routes use broad path patterns; these must be last.
    # `learn` shares the /learn/{slug} pattern with `content`, so learn
    # must come AFTER practice (which has /learn/practice) but BEFORE
    # content (which has /learn/{slug} as the article fallback).
    DISPATCHER_LAST = ("calculators", "learn", "content")

    def _sort_key(module_info: pkgutil.ModuleInfo) -> tuple[int, str]:
        # Tier 0: normal modules, alphabetical (includes practice → /learn/practice).
        # Tier 1: dispatchers with broad patterns, ordered explicitly.
        if module_info.name in DISPATCHER_LAST:
            return (1, str(DISPATCHER_LAST.index(module_info.name)))
        return (0, module_info.name)

    for module_info in sorted(pkgutil.iter_modules([str(_PACKAGE_DIR)]), key=_sort_key):
        if module_info.name.startswith("_"):
            continue

        module = importlib.import_module(f"{_PACKAGE_NAME}.{module_info.name}")
        router = getattr(module, "router", None)

        if router is None:
            logger.warning(
                "Router module %r has no `router` attribute — skipping.",
                module_info.name,
            )
            continue

        if not isinstance(router, APIRouter):
            logger.warning(
                "Router module %r exports `router` but it is not an APIRouter (got %s) — skipping.",
                module_info.name,
                type(router).__name__,
            )
            continue

        logger.debug("Discovered router: %s", module_info.name)
        yield router
