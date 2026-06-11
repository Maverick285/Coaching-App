"""phase 6: tier-5 stake-at-risk per-goal config.

Adds three nullable columns to `goals` so any goal can opt into the
spec's tier-5 stake-at-risk path. Keeps default intervention ceiling
behavior unchanged (Tier 5 is opt-in only).

Idempotent: this migration is recoverable from any partial state. We
inspect the live schema before every op rather than blindly issuing
DDL, so re-running on a DB that already has some of these columns or
the stake_events table is a noop instead of a hard failure. That
matters because the *original* version of this migration had a
self-conflicting index step that left some prod DBs half-applied with
alembic_version still pinned to 0006_phase5.

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


def _existing_columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_indexes(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    goals_cols = _existing_columns("goals")

    # batch_alter_table on SQLite copies the whole table, so it's
    # cheaper to skip entirely when none of the columns we'd add are
    # missing. Common case after a successful first run.
    needed = {
        "stake_webhook_url",
        "stake_webhook_secret",
        "stake_active",
    } - goals_cols

    if needed:
        with op.batch_alter_table("goals") as batch:
            if "stake_webhook_url" in needed:
                batch.add_column(
                    sa.Column("stake_webhook_url", sa.String(length=512), nullable=True)
                )
            if "stake_webhook_secret" in needed:
                batch.add_column(
                    sa.Column("stake_webhook_secret", sa.String(length=256), nullable=True)
                )
            if "stake_active" in needed:
                batch.add_column(
                    sa.Column(
                        "stake_active",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("0"),
                    )
                )

    if "stake_events" not in _existing_tables():
        op.create_table(
            "stake_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("goal_id", sa.Integer(), nullable=False),
            sa.Column("event_kind", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("response_status", sa.Integer(), nullable=True),
            sa.Column("response_body", sa.Text(), nullable=False, server_default=""),
            sa.Column("fired_at", sa.DateTime(), nullable=False),
        )

    if "ix_stake_events_goal_id" not in _existing_indexes("stake_events"):
        op.create_index("ix_stake_events_goal_id", "stake_events", ["goal_id"])


def downgrade() -> None:
    indexes = _existing_indexes("stake_events")
    if "ix_stake_events_goal_id" in indexes:
        op.drop_index("ix_stake_events_goal_id", table_name="stake_events")
    if "stake_events" in _existing_tables():
        op.drop_table("stake_events")
    goals_cols = _existing_columns("goals")
    drop = {"stake_active", "stake_webhook_secret", "stake_webhook_url"} & goals_cols
    if drop:
        with op.batch_alter_table("goals") as batch:
            for col in ("stake_active", "stake_webhook_secret", "stake_webhook_url"):
                if col in drop:
                    batch.drop_column(col)
