"""phase 3: focus sessions, focus check-ins, capture audit log.

Revision ID: 0003_phase3
Revises: 0002_phase2
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_phase3"
down_revision = "0002_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "focus_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("intention", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("planned_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("interventions_fired", sa.Integer(), nullable=False),
    )
    op.create_index("ix_focus_sessions_goal_id", "focus_sessions", ["goal_id"])
    op.create_index("ix_focus_sessions_started_at", "focus_sessions", ["started_at"])
    op.create_index("ix_focus_sessions_state", "focus_sessions", ["state"])

    op.create_table(
        "focus_check_ins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("fired_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=False),
    )
    op.create_index("ix_focus_check_ins_session_id", "focus_check_ins", ["session_id"])

    op.create_table(
        "capture_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("proposed_actions", sa.JSON(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_capture_logs_received_at", "capture_logs", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_capture_logs_received_at", table_name="capture_logs")
    op.drop_table("capture_logs")
    op.drop_index("ix_focus_check_ins_session_id", table_name="focus_check_ins")
    op.drop_table("focus_check_ins")
    op.drop_index("ix_focus_sessions_state", table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_started_at", table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_goal_id", table_name="focus_sessions")
    op.drop_table("focus_sessions")
