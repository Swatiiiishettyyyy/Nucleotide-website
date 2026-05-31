"""Repair cart_coupons table expected by genetic cart coupon service

Revision ID: 091_repair_cart_coupons_table
Revises: 090_add_cart_item_product_type
Create Date: 2026-05-24
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa


revision: str = "091_repair_cart_coupons_table"
down_revision: Union[str, None] = "090_add_cart_item_product_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _indexes(inspector: sa.Inspector, table_name: str) -> Set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "cart_coupons" in tables:
        return

    op.create_table(
        "cart_coupons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("coupon_id", sa.Integer(), nullable=False),
        sa.Column("coupon_code", sa.String(length=50), nullable=False),
        sa.Column("discount_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_cart_coupons_id", "cart_coupons", ["id"], unique=False)
    op.create_index("ix_cart_coupons_user_id", "cart_coupons", ["user_id"], unique=False)
    op.create_index("ix_cart_coupons_coupon_id", "cart_coupons", ["coupon_id"], unique=False)
    op.create_index("ix_cart_coupons_coupon_code", "cart_coupons", ["coupon_code"], unique=False)

    if "coupons" in tables:
        op.create_foreign_key(
            "fk_cart_coupons_coupon_id",
            "cart_coupons",
            "coupons",
            ["coupon_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    pass
