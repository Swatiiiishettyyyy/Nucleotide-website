"""Repair orders columns expected by current models

Revision ID: 089_repair_orders_model_columns
Revises: 088_remove_member_associated_category_fields
Create Date: 2026-05-24
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa


revision: str = "089_repair_orders_model_columns"
down_revision: Union[str, None] = "088_remove_member_associated_category_fields"
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

    if "orders" not in inspector.get_table_names():
        return

    order_columns = _columns(inspector, "orders")
    order_indexes = _indexes(inspector, "orders")

    if "delivery_charge" not in order_columns:
        op.add_column("orders", sa.Column("delivery_charge", sa.Float(), nullable=False, server_default="0.0"))

    if "discount" not in order_columns:
        op.add_column("orders", sa.Column("discount", sa.Float(), nullable=True, server_default="0.0"))

    if "coupon_code" not in order_columns:
        op.add_column("orders", sa.Column("coupon_code", sa.String(length=50), nullable=True))
        if "ix_orders_coupon_code" not in order_indexes:
            op.create_index("ix_orders_coupon_code", "orders", ["coupon_code"], unique=False)

    if "coupon_discount" not in order_columns:
        op.add_column("orders", sa.Column("coupon_discount", sa.Float(), nullable=True, server_default="0.0"))

    if "razorpay_customer_id" not in order_columns:
        op.add_column("orders", sa.Column("razorpay_customer_id", sa.String(length=255), nullable=True))
        if "ix_orders_razorpay_customer_id" not in order_indexes:
            op.create_index("ix_orders_razorpay_customer_id", "orders", ["razorpay_customer_id"], unique=False)

    if "razorpay_invoice_id" not in order_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_id", sa.String(length=255), nullable=True))
        if "ix_orders_razorpay_invoice_id" not in order_indexes:
            op.create_index("ix_orders_razorpay_invoice_id", "orders", ["razorpay_invoice_id"], unique=False)

    if "razorpay_invoice_number" not in order_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_number", sa.String(length=255), nullable=True))

    if "razorpay_invoice_url" not in order_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_url", sa.String(length=500), nullable=True))

    if "razorpay_invoice_status" not in order_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_status", sa.String(length=50), nullable=True))
        if "ix_orders_razorpay_invoice_status" not in order_indexes:
            op.create_index("ix_orders_razorpay_invoice_status", "orders", ["razorpay_invoice_status"], unique=False)


def downgrade() -> None:
    pass
