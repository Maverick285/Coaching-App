"""phase 4: agent reports, interventions, distraction rules.

Revision ID: 0004_phase4
Revises: 0003_phase3
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_phase4"
down_revision = "0003_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("foreground_category", sa.String(length=64), nullable=False),
        sa.Column("foreground_app_hint", sa.String(length=256), nullable=False),
        sa.Column("idle_seconds", sa.Integer(), nullable=False),
        sa.Column("active_seconds", sa.Integer(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_agent_reports_received_at", "agent_reports", ["received_at"])
    op.create_index("ix_agent_reports_session_id", "agent_reports", ["session_id"])

    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("fired_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("next_escalation_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
    )
    op.create_index("ix_interventions_session_id", "interventions", ["session_id"])
    op.create_index("ix_interventions_goal_id", "interventions", ["goal_id"])
    op.create_index("ix_interventions_fired_at", "interventions", ["fired_at"])

    op.create_table(
        "distraction_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("distractor_category", sa.String(length=64), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_distraction_rules_goal_id", "distraction_rules", ["goal_id"])


def downgrade() -> None:
    op.drop_index("ix_distraction_rules_goal_id", table_name="distraction_rules")
    op.drop_table("distraction_rules")
    op.drop_index("ix_interventions_fired_at", table_name="interventions")
    op.drop_index("ix_interventions_goal_id", table_name="interventions")
    op.drop_index("ix_interventions_session_id", table_name="interventions")
    op.drop_table("interventions")
    op.drop_index("ix_agent_reports_session_id", table_name="agent_reports")
    op.drop_index("ix_agent_reports_received_at", table_name="agent_reports")
    op.drop_table("agent_reports")
