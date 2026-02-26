"""add serviceable_locations table

Revision ID: 053_add_serviceable_locations
Revises: 052_remove_referral_hashed
Create Date: 2026-02-18

Tags: address, schema, serviceable_locations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "053_add_serviceable_locations"
down_revision: Union[str, None] = "052_remove_referral_hashed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "serviceable_locations" not in tables:
        op.create_table(
            "serviceable_locations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("location", sa.String(length=150), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("location", name="uq_serviceable_locations_location"),
        )
        op.create_index(op.f("ix_serviceable_locations_id"), "serviceable_locations", ["id"], unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "serviceable_locations" in tables:
        op.drop_index(op.f("ix_serviceable_locations_id"), table_name="serviceable_locations")
        op.drop_table("serviceable_locations")
