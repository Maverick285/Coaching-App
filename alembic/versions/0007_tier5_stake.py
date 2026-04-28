"""phase 6: tier-5 stake-at-risk per-goal config.

Adds three nullable columns to `goals` so any goal can opt into the
spec's tier-5 stake-at-risk path. Keeps default intervention ceiling
behavior unchanged (Tier 5 is opt-in only).

Revision ID: 0007_tier5_stake
Revises: 0006_phase5
Create Date: 2026-04-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_tier5_stake"
down_revision = "0006_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("goals") as batch:
        batch.add_column(
            sa.Column("stake_webhook_url", sa.String(length=512), nullable=True)
        )
        batch.add_column(
            sa.Column("stake_webhook_secret", sa.String(length=256), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "stake_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )

    op.create_table(
        "stake_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False, index=True),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("fired_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stake_events_goal_id", "stake_events", ["goal_id"])


def downgrade() -> None:
    op.drop_index("ix_stake_events_goal_id", table_name="stake_events")
    op.drop_table("stake_events")
    with op.batch_alter_table("goals") as batch:
        batch.drop_column("stake_active")
        batch.drop_column("stake_webhook_secret")
        batch.drop_column("stake_webhook_url")
