"""remove username and password from users

Revision ID: 051_remove_username_password
Revises: 050_add_notifications_enabled
Create Date: 2026-02-18

Tags: users, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "051_remove_username_password"
down_revision: Union[str, None] = "050_add_notifications_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "users" not in inspector.get_table_names():
        return
    users_columns = {c["name"] for c in inspector.get_columns("users")}
    if "username" in users_columns:
        op.drop_column("users", "username")
    if "password" in users_columns:
        op.drop_column("users", "password")


def downgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("password", sa.String(255), nullable=True))
