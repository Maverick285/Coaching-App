"""phase 7: daily plan + plan items.

Adds two tables to support the "Coach me today" daily-plan flow.
On each new day's first Today-screen mount, the backend generates a
plan: a list of goal-derived tasks tiered Must / Should / Could,
each with an estimated time commitment. The user sees these as
swipeable cards on Today and can mark each Done, Later, Skipped,
or attach a free-text reason ("I'll do that tomorrow while in OKC")
that the system parses and respects on future plans.

Revision ID: 0008_daily_plan
Revises: 0007_tier5_stake
Create Date: 2026-04-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_daily_plan"
down_revision = "0007_tier5_stake"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "daily_plans" not in _existing_tables():
        op.create_table(
            "daily_plans",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_date", sa.Date(), nullable=False, unique=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_daily_plans_plan_date", "daily_plans", ["plan_date"])

    if "daily_plan_items" not in _existing_tables():
        op.create_table(
            "daily_plan_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("goal_id", sa.Integer(), nullable=False),
            sa.Column("task_text", sa.Text(), nullable=False),
            sa.Column("tier", sa.String(length=16), nullable=False),  # must|should|could
            sa.Column("est_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
            sa.Column("state", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("defer_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("defer_until", sa.Date(), nullable=True),
            sa.Column("defer_context", sa.Text(), nullable=False, server_default=""),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_daily_plan_items_plan_id", "daily_plan_items", ["plan_id"])
        op.create_index("ix_daily_plan_items_goal_id", "daily_plan_items", ["goal_id"])


def downgrade() -> None:
    if "daily_plan_items" in _existing_tables():
        op.drop_index("ix_daily_plan_items_goal_id", table_name="daily_plan_items")
        op.drop_index("ix_daily_plan_items_plan_id", table_name="daily_plan_items")
        op.drop_table("daily_plan_items")
    if "daily_plans" in _existing_tables():
        op.drop_index("ix_daily_plans_plan_date", table_name="daily_plans")
        op.drop_table("daily_plans")
