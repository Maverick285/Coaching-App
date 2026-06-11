"""phase 2: goals, tasks, intentions, progress logs, day grades, journal.

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("approach", sa.String(length=32), nullable=False),
        sa.Column("plan_source", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("intervention_ceiling", sa.Integer(), nullable=False),
        sa.Column("pace_target_unit", sa.String(length=64), nullable=False),
        sa.Column("pace_target_amount", sa.Float(), nullable=False),
        sa.Column("pace_target_description", sa.Text(), nullable=False),
        sa.Column("mvp_threshold", sa.Text(), nullable=False),
        sa.Column("parent_goal_id", sa.Integer(), nullable=True),
        sa.Column("reflection_log", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_goals_state", "goals", ["state"])
    op.create_index("ix_goals_parent_goal_id", "goals", ["parent_goal_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("definition_of_done", sa.Text(), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("triggering_intention_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("first_60_seconds", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tasks_goal_id", "tasks", ["goal_id"])
    op.create_index("ix_tasks_state", "tasks", ["state"])

    op.create_table(
        "implementation_intentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("cue_type", sa.String(length=16), nullable=False),
        sa.Column("cue_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_intentions_goal_id", "implementation_intentions", ["goal_id"])
    op.create_index("ix_intentions_task_id", "implementation_intentions", ["task_id"])

    op.create_table(
        "progress_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("attributed_units", sa.Float(), nullable=False),
        sa.Column("unit_label", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
    )
    op.create_index("ix_progress_logs_goal_id", "progress_logs", ["goal_id"])
    op.create_index("ix_progress_logs_recorded_at", "progress_logs", ["recorded_at"])

    op.create_table(
        "day_grades",
        sa.Column("grade_date", sa.Date(), primary_key=True),
        sa.Column("system_score", sa.Float(), nullable=False),
        sa.Column("user_score", sa.Float(), nullable=True),
        sa.Column("per_goal_scores", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("user_notes", sa.Text(), nullable=False),
        sa.Column("is_zero_day", sa.Boolean(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "journal_entries",
        sa.Column("entry_date", sa.Date(), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mood", sa.String(length=32), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("journal_entries")
    op.drop_table("day_grades")
    op.drop_index("ix_progress_logs_recorded_at", table_name="progress_logs")
    op.drop_index("ix_progress_logs_goal_id", table_name="progress_logs")
    op.drop_table("progress_logs")
    op.drop_index("ix_intentions_task_id", table_name="implementation_intentions")
    op.drop_index("ix_intentions_goal_id", table_name="implementation_intentions")
    op.drop_table("implementation_intentions")
    op.drop_index("ix_tasks_state", table_name="tasks")
    op.drop_index("ix_tasks_goal_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_goals_parent_goal_id", table_name="goals")
    op.drop_index("ix_goals_state", table_name="goals")
    op.drop_table("goals")
