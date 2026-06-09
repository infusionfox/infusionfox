"""InfusionFox business-logic services.

Modules here encapsulate side-effecting workflows that don't belong in a
thin route handler — DB writes for audit purposes, multi-step operations,
or reconciliation logic. Keep these free of FastAPI imports so they're
easy to call from scripts and tests.
"""
