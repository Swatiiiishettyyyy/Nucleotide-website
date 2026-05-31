"""Add product plan type and max members columns

Revision ID: 057_product_plan_members
Revises: 056_add_coupon_allowed_users
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa


revision = "057_product_plan_members"
down_revision = "056_add_coupon_allowed_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "products" not in inspector.get_table_names():
        return

    product_columns = {column["name"] for column in inspector.get_columns("products")}

    if "plan_type" not in product_columns:
        op.add_column(
            "products",
            sa.Column(
                "plan_type",
                sa.Enum("SINGLE", "COUPLE", "FAMILY", name="plantype"),
                nullable=False,
                server_default="SINGLE",
            ),
        )
        op.create_index("ix_products_plan_type", "products", ["plan_type"], unique=False)

    if "max_members" not in product_columns:
        op.add_column(
            "products",
            sa.Column("max_members", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "products" not in inspector.get_table_names():
        return

    product_columns = {column["name"] for column in inspector.get_columns("products")}
    indexes = {index["name"] for index in inspector.get_indexes("products")}

    if "max_members" in product_columns:
        op.drop_column("products", "max_members")

    if "plan_type" in product_columns:
        if "ix_products_plan_type" in indexes:
            op.drop_index("ix_products_plan_type", table_name="products")
        op.drop_column("products", "plan_type")
