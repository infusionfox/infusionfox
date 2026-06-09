"""
Observability — Sentry error tracking initialization.

Sentry captures unhandled exceptions (the 500s that matter) and ships them
to sentry.io with full request context, stack trace, and local variables.
This is what catches the "vet hit a 500 in production" failure mode that
otherwise only surfaces via emails from confused users.

This module is a no-op when SENTRY_DSN is unset, so local development,
the test suite, and any non-production deploy do not transmit data to
Sentry. Production deploys set SENTRY_DSN (and optionally INFUSIONFOX_ENV
and INFUSIONFOX_RELEASE) via container environment variables.

Defaults chosen for the clinical context:

- `send_default_pii=False`: vets type patient names into the anesthesia
  worksheet's "Name / ID" field and into feedback messages. Without this
  default, request bodies and form data would attach to every error event
  and leak third-party patient info to Sentry. The default leaves room
  for a controlled, explicit opt-in later if we ever need richer context.
- `traces_sample_rate=0`: errors-only. Performance tracing adds cost
  (Sentry quota, response latency) for value we don't currently need.
- `attach_stacktrace=False`: stack traces auto-attach to *exceptions*
  but not to bare log messages, which is the conservative default and
  matches what we want.
"""

from __future__ import annotations

import os

# Module-level guard so repeated calls (tests importing this module
# multiple times, or future hot-reload scenarios) don't reinitialize.
_initialized: bool = False


def init_sentry(release: str | None = None) -> bool:
    """Initialize Sentry if SENTRY_DSN is set. No-op otherwise.

    Call this once at startup, BEFORE FastAPI's app is constructed —
    Sentry's FastAPI integration patches `fastapi.routing.get_request_handler`
    at init time, and patches applied after app construction don't take
    effect for handlers that were already wired.

    Args:
        release: Optional release identifier (typically the app version
            or a git SHA). Sentry tags every event with this so you can
            tell which deployed version produced the error. Falls back
            to the INFUSIONFOX_RELEASE env var if not provided.

    Returns:
        True if Sentry was initialized; False if SENTRY_DSN was unset.
    """
    global _initialized
    if _initialized:
        return True

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    # Import here so the SDK is only loaded when actually needed. Keeps
    # `pytest` startup fast and means the cost is only paid in production.
    import sentry_sdk

    environment = os.environ.get("INFUSIONFOX_ENV", "production").strip() or "production"
    resolved_release = release or os.environ.get("INFUSIONFOX_RELEASE", "").strip() or None

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=resolved_release,
        # Errors only — no performance traces. InfusionFox's request volume
        # makes performance monitoring unhelpful versus its quota cost.
        # Set to 0.0 explicitly rather than omitting it so the intent is
        # readable at the call site.
        traces_sample_rate=0.0,
        # Do not attach request bodies, IPs, headers, or form data to
        # error events by default. Form fields can contain patient names
        # (Anesthesia worksheet, feedback messages); we don't want that
        # leaving the server. If you later need richer debugging context,
        # use sentry_sdk.set_context() inside specific handlers rather
        # than flipping this globally.
        send_default_pii=False,
        # Auto-detect FastAPI + Starlette + SQLAlchemy integrations. Each
        # one only activates if its underlying library is installed, which
        # it always is here.
        auto_enabling_integrations=True,
    )
    _initialized = True
    return True
