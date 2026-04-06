"""Add coupon_usages table and allowed_plan_types to coupons

Revision ID: 055_add_coupon_usages_and_plan_types
Revises: 068_thyrocare_sku_id
Create Date: 2026-04-03

Tags: coupons, schema
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "055_add_coupon_usages_and_plan_types"
down_revision: Union[str, None] = "7b9cfffc6882"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. Add allowed_plan_types column to coupons
    coupons_cols = [c["name"] for c in inspector.get_columns("coupons")]
    if "allowed_plan_types" not in coupons_cols:
        op.add_column("coupons", sa.Column("allowed_plan_types", sa.String(255), nullable=True))

    # 2. Create coupon_usages table
    existing_tables = inspector.get_table_names()
    if "coupon_usages" not in existing_tables:
        op.create_table(
            "coupon_usages",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("coupon_id", sa.Integer, sa.ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("coupon_code", sa.String(50), nullable=False, index=True),
            sa.Column("user_id", sa.Integer, nullable=False, index=True),
            sa.Column("order_id", sa.Integer, nullable=False, index=True),
            sa.Column("order_number", sa.String(50), nullable=False),
            sa.Column("discount_amount", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_tables = inspector.get_table_names()
    if "coupon_usages" in existing_tables:
        op.drop_table("coupon_usages")

    coupons_cols = [c["name"] for c in inspector.get_columns("coupons")]
    if "allowed_plan_types" in coupons_cols:
        op.drop_column("coupons", "allowed_plan_types")
