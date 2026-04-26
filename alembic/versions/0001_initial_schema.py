"""initial schema for buddy phase 0.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indexed_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(), nullable=False),
        sa.Column("doc_metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("path", name="uq_indexed_documents_path"),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_path", sa.String(length=512), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("chunk_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_path", "chunk_index", name="uq_doc_chunk"),
    )
    op.create_index(
        "ix_document_chunks_document_path",
        "document_chunks",
        ["document_path"],
    )

    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
    )
    op.create_index("ix_api_usage_occurred_at", "api_usage", ["occurred_at"])

    op.create_table(
        "memory_proposals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("proposal_kind", sa.String(length=64), nullable=False),
        sa.Column("target_path", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("proposed_content", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("proposal_metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_memory_proposals_created_at",
        "memory_proposals",
        ["created_at"],
    )

    op.create_table(
        "conversations",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("log_path", sa.String(length=512), nullable=False),
    )
    op.create_index("ix_conversations_started_at", "conversations", ["started_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("memory_loaded", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_conversation_messages_session_id",
        "conversation_messages",
        ["session_id"],
    )

    op.create_table(
        "intake_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("transcript", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("intake_sessions")
    op.drop_index("ix_conversation_messages_session_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_started_at", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_memory_proposals_created_at", table_name="memory_proposals")
    op.drop_table("memory_proposals")
    op.drop_index("ix_api_usage_occurred_at", table_name="api_usage")
    op.drop_table("api_usage")
    op.drop_index("ix_document_chunks_document_path", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("indexed_documents")
