"""remove referral_code and hashedpassword from users

Revision ID: 052_remove_referral_hashed
Revises: 051_remove_username_password
Create Date: 2026-02-18

Tags: users, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "052_remove_referral_hashed"
down_revision: Union[str, None] = "051_remove_username_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "users" not in inspector.get_table_names():
        return
    users_columns = {c["name"] for c in inspector.get_columns("users")}
    for col in ("referral_code", "refreal_code", "hashedpassword", "hashed_password"):
        if col in users_columns:
            op.drop_column("users", col)


def downgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("hashedpassword", sa.String(255), nullable=True))
