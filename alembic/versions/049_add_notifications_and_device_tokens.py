"""add notifications and user_device_tokens tables

Revision ID: 049_add_notifications_and_device (32 chars for DB)
Revises: 048_add_razorpay_invoice_fields_
Create Date: 2026-02-12

Tags: notifications, fcm, device_tokens, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "049_add_notifications_and_device"  # 31 chars - fits alembic_version.version_num(32)
down_revision: Union[str, None] = "048_add_razorpay_invoice_fields_"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
        op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)

    if "user_device_tokens" not in tables:
        op.create_table(
            "user_device_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("device_token", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("device_token", name="uq_user_device_tokens_device_token"),
        )
        op.create_index(op.f("ix_user_device_tokens_id"), "user_device_tokens", ["id"], unique=False)
        op.create_index(op.f("ix_user_device_tokens_user_id"), "user_device_tokens", ["user_id"], unique=False)
        op.create_index(op.f("ix_user_device_tokens_device_token"), "user_device_tokens", ["device_token"], unique=True)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "user_device_tokens" in tables:
        op.drop_index(op.f("ix_user_device_tokens_device_token"), table_name="user_device_tokens")
        op.drop_index(op.f("ix_user_device_tokens_user_id"), table_name="user_device_tokens")
        op.drop_index(op.f("ix_user_device_tokens_id"), table_name="user_device_tokens")
        op.drop_table("user_device_tokens")

    if "notifications" in tables:
        op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
        op.drop_table("notifications")
