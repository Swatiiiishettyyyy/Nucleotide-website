"""add api_key to members table

Revision ID: 046_add_member_api_key
Revises: 045_add_tracking_records_table
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "046_add_member_api_key"
down_revision = "045_add_tracking_records_table"
branch_labels = None
depends_on = None


def upgrade():
    """Add api_key column and index to members table if it doesn't exist."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "members" in tables:
        members_columns = {col["name"]: col for col in inspector.get_columns("members")}

        if "api_key" not in members_columns:
            op.add_column(
                "members",
                sa.Column("api_key", sa.String(length=128), nullable=True),
            )
            # Create a unique index for fast lookup and to enforce uniqueness
            op.create_index(
                "ix_members_api_key",
                "members",
                ["api_key"],
                unique=True,
            )


def downgrade():
    """Remove api_key column and its index from members table."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "members" in tables:
        members_columns = {col["name"]: col for col in inspector.get_columns("members")}

        # Drop index first if it exists
        indexes = {idx["name"]: idx for idx in inspector.get_indexes("members")}
        if "ix_members_api_key" in indexes:
            op.drop_index("ix_members_api_key", table_name="members")

        if "api_key" in members_columns:
            op.drop_column("members", "api_key")


