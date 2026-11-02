"""initial schema for the IT service desk

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False, index=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tickets",
        sa.Column("ticket_id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("category", sa.String(32), nullable=False, index=True),
        sa.Column("priority", sa.String(8), nullable=False, index=True, server_default="p3"),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("assignee_group", sa.String(64), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("tickets.ticket_id"), index=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.String(32), primary_key=True),
        sa.Column("asset_type", sa.String(32), nullable=False, index=True),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("serial_no", sa.String(64), nullable=False, index=True),
        sa.Column("owner_user_id", sa.String(64), nullable=True, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("warranty_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(64), nullable=False, server_default=""),
    )
    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.String(32), primary_key=True),
        sa.Column(
            "ticket_id", sa.String(32), sa.ForeignKey("tickets.ticket_id"), nullable=True, index=True
        ),
        sa.Column("requester_id", sa.String(64), nullable=False, index=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target", sa.String(128), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, index=True, server_default="pending"),
        sa.Column("approver_role", sa.String(32), nullable=False, server_default="manager"),
        sa.Column("approver_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for table in [
        "approvals",
        "assets",
        "ticket_events",
        "tickets",
        "idempotency_keys",
        "audit_logs",
        "messages",
        "sessions",
    ]:
        op.drop_table(table)
