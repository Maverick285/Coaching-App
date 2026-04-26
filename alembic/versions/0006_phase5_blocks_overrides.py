"""phase 5: blocked-app rules + override requests.

Revision ID: 0006_phase5
Revises: 0005_preferences
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_phase5"
down_revision = "0005_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blocked_app_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(length=256), nullable=False),
        sa.Column("block_tier", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_blocked_app_rules_goal_id", "blocked_app_rules", ["goal_id"])

    op.create_table(
        "override_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("intervention_id", sa.Integer(), nullable=True),
        sa.Column("package_name", sa.String(length=256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("approver_label", sa.String(length=64), nullable=False),
        sa.Column("sms_status", sa.String(length=32), nullable=False),
        sa.Column("sms_detail", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("active_minutes", sa.Integer(), nullable=False),
    )
    op.create_index("ix_override_requests_requested_at", "override_requests", ["requested_at"])
    op.create_index("ix_override_requests_session_id", "override_requests", ["session_id"])
    op.create_index("ix_override_requests_goal_id", "override_requests", ["goal_id"])
    op.create_index("ix_override_requests_status", "override_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_override_requests_status", table_name="override_requests")
    op.drop_index("ix_override_requests_goal_id", table_name="override_requests")
    op.drop_index("ix_override_requests_session_id", table_name="override_requests")
    op.drop_index("ix_override_requests_requested_at", table_name="override_requests")
    op.drop_table("override_requests")
    op.drop_index("ix_blocked_app_rules_goal_id", table_name="blocked_app_rules")
    op.drop_table("blocked_app_rules")
