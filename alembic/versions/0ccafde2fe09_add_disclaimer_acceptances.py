"""add disclaimer_acceptances table

Revision ID: 0ccafde2fe09
Revises: c2641fe6cefd
Create Date: 2026-06-06 14:00:00.000000

Creates the audit-trail table for the hard-block disclaimer modal.
Every accepted disclaimer is one row: who (IP + UA + opaque session
token), what version, when.

This is the only intentionally-PII-bearing table in infusionfox. The
disclaimer text itself discloses the IP/UA/timestamp collection
BEFORE the row is written. No analytics or tracking elsewhere.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0ccafde2fe09"
down_revision: str | Sequence[str] | None = "c2641fe6cefd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "disclaimer_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "disclaimer_version", sa.String(length=32), nullable=False
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("session_token", sa.String(length=64), nullable=True),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_disclaimer_acceptances_disclaimer_version",
        "disclaimer_acceptances",
        ["disclaimer_version"],
    )
    op.create_index(
        "ix_disclaimer_acceptances_ip_address",
        "disclaimer_acceptances",
        ["ip_address"],
    )
    op.create_index(
        "ix_disclaimer_acceptances_session_token",
        "disclaimer_acceptances",
        ["session_token"],
    )
    op.create_index(
        "ix_disclaimer_acceptances_accepted_at",
        "disclaimer_acceptances",
        ["accepted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_disclaimer_acceptances_accepted_at",
        table_name="disclaimer_acceptances",
    )
    op.drop_index(
        "ix_disclaimer_acceptances_session_token",
        table_name="disclaimer_acceptances",
    )
    op.drop_index(
        "ix_disclaimer_acceptances_ip_address",
        table_name="disclaimer_acceptances",
    )
    op.drop_index(
        "ix_disclaimer_acceptances_disclaimer_version",
        table_name="disclaimer_acceptances",
    )
    op.drop_table("disclaimer_acceptances")
