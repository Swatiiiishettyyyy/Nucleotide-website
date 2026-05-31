"""Add product_type to cart items

Revision ID: 090_add_cart_item_product_type
Revises: 089_repair_orders_model_columns
Create Date: 2026-05-24
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa


revision: str = "090_add_cart_item_product_type"
down_revision: Union[str, None] = "089_repair_orders_model_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table_name: str) -> Set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector: sa.Inspector, table_name: str) -> Set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "cart_items" not in inspector.get_table_names():
        return

    cart_item_columns = _columns(inspector, "cart_items")
    cart_item_indexes = _indexes(inspector, "cart_items")

    if "product_type" not in cart_item_columns:
        op.add_column(
            "cart_items",
            sa.Column(
                "product_type",
                sa.String(length=20),
                nullable=False,
                server_default="genetic",
            ),
        )

    if "ix_cart_items_product_type" not in cart_item_indexes:
        op.create_index(
            "ix_cart_items_product_type",
            "cart_items",
            ["product_type"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "cart_items" not in inspector.get_table_names():
        return

    cart_item_columns = _columns(inspector, "cart_items")
    cart_item_indexes = _indexes(inspector, "cart_items")

    if "ix_cart_items_product_type" in cart_item_indexes:
        op.drop_index("ix_cart_items_product_type", table_name="cart_items")

    if "product_type" in cart_item_columns:
        op.drop_column("cart_items", "product_type")
