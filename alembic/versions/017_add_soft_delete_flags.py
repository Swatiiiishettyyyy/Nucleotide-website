"""add soft delete flags to core entities

Revision ID: 017_add_soft_delete_flags
Revises: 016_add_consent_products
Create Date: 2025-12-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "017_add_soft_delete_flags"
down_revision = "016_add_consent_products"
branch_labels = None
depends_on = None


def upgrade():
    # Addresses
    op.add_column(
        "addresses",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "addresses",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Members
    op.add_column(
        "members",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "members",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Products
    op.add_column(
        "products",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "products",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    # Products
    op.drop_column("products", "deleted_at")
    op.drop_column("products", "is_deleted")

    # Members
    op.drop_column("members", "deleted_at")
    op.drop_column("members", "is_deleted")

    # Addresses
    op.drop_column("addresses", "deleted_at")
    op.drop_column("addresses", "is_deleted")

