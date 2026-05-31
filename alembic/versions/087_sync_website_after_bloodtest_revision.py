"""Sync website schema after shared blood-test revision

Revision ID: 087_sync_website_after_bt
Revises: 086_add_blood_test_coupon_fields_to_orders
Create Date: 2026-05-24
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa


revision: str = "087_sync_website_after_bt"
down_revision: Union[str, None] = "086_add_blood_test_coupon_fields_to_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table_name: str) -> Set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "coupons" in tables:
        coupon_columns = _columns(inspector, "coupons")
        if "allowed_plan_types" not in coupon_columns:
            op.add_column("coupons", sa.Column("allowed_plan_types", sa.String(255), nullable=True))

        if "coupon_usages" not in tables:
            op.create_table(
                "coupon_usages",
                sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                sa.Column("coupon_id", sa.Integer(), nullable=False),
                sa.Column("coupon_code", sa.String(50), nullable=False),
                sa.Column("user_id", sa.Integer(), nullable=False),
                sa.Column("order_id", sa.Integer(), nullable=False),
                sa.Column("order_number", sa.String(50), nullable=False),
                sa.Column("discount_amount", sa.Float(), nullable=False, server_default="0.0"),
                sa.Column("used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
            )
            op.create_index("ix_coupon_usages_coupon_id", "coupon_usages", ["coupon_id"])
            op.create_index("ix_coupon_usages_coupon_code", "coupon_usages", ["coupon_code"])
            op.create_index("ix_coupon_usages_user_id", "coupon_usages", ["user_id"])
            op.create_index("ix_coupon_usages_order_id", "coupon_usages", ["order_id"])

        if "coupon_allowed_users" not in tables:
            op.create_table(
                "coupon_allowed_users",
                sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
                sa.Column("coupon_id", sa.Integer(), nullable=False),
                sa.Column("user_id", sa.Integer(), nullable=True),
                sa.Column("mobile", sa.String(100), nullable=True),
                sa.PrimaryKeyConstraint("id"),
                sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
                sa.UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user_id"),
                sa.UniqueConstraint("coupon_id", "mobile", name="uq_coupon_mobile"),
                sa.CheckConstraint(
                    "user_id IS NOT NULL OR mobile IS NOT NULL",
                    name="ck_coupon_allowed_users_not_both_null",
                ),
            )
            op.create_index("ix_coupon_allowed_users_coupon_id", "coupon_allowed_users", ["coupon_id"])
            op.create_index("ix_coupon_allowed_users_user_id", "coupon_allowed_users", ["user_id"])
            op.create_index("ix_coupon_allowed_users_mobile", "coupon_allowed_users", ["mobile"])

    if "products" in tables:
        product_columns = _columns(inspector, "products")
        product_indexes = {index["name"] for index in inspector.get_indexes("products")}

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
        if "ix_products_plan_type" not in product_indexes:
            op.create_index("ix_products_plan_type", "products", ["plan_type"], unique=False)

        if "max_members" not in product_columns:
            op.add_column(
                "products",
                sa.Column("max_members", sa.Integer(), nullable=False, server_default="1"),
            )


def downgrade() -> None:
    pass
