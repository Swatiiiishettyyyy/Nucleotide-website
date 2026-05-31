"""Drop unused order delivery, discount, and Razorpay invoice columns.

Revision ID: 093_drop_order_invoice_cols
Revises: 092_repair_genetic_coupon_tables
Create Date: 2026-05-25
"""
from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "093_drop_order_invoice_cols"
down_revision: Union[str, None] = "092_repair_genetic_coupon_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DROP_COLUMNS = (
    "delivery_charge",
    "discount",
    "razorpay_customer_id",
    "razorpay_invoice_id",
    "razorpay_invoice_number",
    "razorpay_invoice_url",
    "razorpay_invoice_status",
)

DROP_INDEXES = (
    "ix_orders_razorpay_customer_id",
    "ix_orders_razorpay_invoice_id",
    "ix_orders_razorpay_invoice_status",
)


def _columns() -> Set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns("orders")}


def _indexes() -> Set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes("orders")}


def upgrade() -> None:
    indexes = _indexes()
    for index_name in DROP_INDEXES:
        if index_name in indexes:
            op.drop_index(index_name, table_name="orders")

    columns = _columns()
    for column_name in DROP_COLUMNS:
        if column_name in columns:
            op.drop_column("orders", column_name)


def downgrade() -> None:
    columns = _columns()

    def add_if_missing(column: sa.Column) -> None:
        if column.name not in columns:
            op.add_column("orders", column)

    add_if_missing(sa.Column("delivery_charge", sa.Float(), nullable=True, server_default="0.0"))
    add_if_missing(sa.Column("discount", sa.Float(), nullable=True, server_default="0.0"))
    add_if_missing(sa.Column("razorpay_customer_id", sa.String(length=255), nullable=True))
    add_if_missing(sa.Column("razorpay_invoice_id", sa.String(length=255), nullable=True))
    add_if_missing(sa.Column("razorpay_invoice_number", sa.String(length=255), nullable=True))
    add_if_missing(sa.Column("razorpay_invoice_url", sa.String(length=500), nullable=True))
    add_if_missing(sa.Column("razorpay_invoice_status", sa.String(length=50), nullable=True))

    indexes = _indexes()
    if "ix_orders_razorpay_customer_id" not in indexes:
        op.create_index("ix_orders_razorpay_customer_id", "orders", ["razorpay_customer_id"])
    if "ix_orders_razorpay_invoice_id" not in indexes:
        op.create_index("ix_orders_razorpay_invoice_id", "orders", ["razorpay_invoice_id"])
    if "ix_orders_razorpay_invoice_status" not in indexes:
        op.create_index("ix_orders_razorpay_invoice_status", "orders", ["razorpay_invoice_status"])
