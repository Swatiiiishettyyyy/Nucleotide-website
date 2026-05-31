"""Drop legacy provider/Thyrocare columns from genetic order items.

Revision ID: 094_drop_genetic_item_provider_cols
Revises: 093_drop_order_invoice_cols
Create Date: 2026-05-25
"""
from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "094_drop_genetic_item_provider_cols"
down_revision: Union[str, None] = "093_drop_order_invoice_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "genetic_order_items"

DROP_COLUMNS = (
    "provider_metadata",
    "thyrocare_lead_id",
    "thyrocare_sku_id",
    "thyrocare_order_id",
    "thyrocare_product_id",
    "thyrocare_booking_status",
    "thyrocare_booking_error",
)

DROP_INDEXES = (
    "ix_genetic_order_items_provider_metadata",
    "ix_genetic_order_items_thyrocare_lead_id",
    "ix_genetic_order_items_thyrocare_sku_id",
    "ix_genetic_order_items_thyrocare_order_id",
    "ix_genetic_order_items_thyrocare_product_id",
    "ix_genetic_order_items_thyrocare_booking_status",
    "ix_genetic_order_items_thyrocare_booking_error",
)


def _has_table() -> bool:
    return TABLE_NAME in inspect(op.get_bind()).get_table_names()


def _columns() -> Set[str]:
    if not _has_table():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(TABLE_NAME)}


def _indexes() -> Set[str]:
    if not _has_table():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE_NAME)}


def _drop_foreign_keys_on_drop_columns() -> None:
    inspector = inspect(op.get_bind())
    drop_column_set = set(DROP_COLUMNS)
    for fk in inspector.get_foreign_keys(TABLE_NAME):
        fk_columns = set(fk.get("constrained_columns") or [])
        fk_name = fk.get("name")
        if fk_name and fk_columns.intersection(drop_column_set):
            op.drop_constraint(fk_name, TABLE_NAME, type_="foreignkey")


def upgrade() -> None:
    if not _has_table():
        return

    _drop_foreign_keys_on_drop_columns()

    indexes = _indexes()
    for index_name in DROP_INDEXES:
        if index_name in indexes:
            op.drop_index(index_name, table_name=TABLE_NAME)

    columns = _columns()
    for column_name in DROP_COLUMNS:
        if column_name in columns:
            op.drop_column(TABLE_NAME, column_name)


def downgrade() -> None:
    if not _has_table():
        return

    columns = _columns()

    def add_if_missing(column: sa.Column) -> None:
        if column.name not in columns:
            op.add_column(TABLE_NAME, column)

    add_if_missing(sa.Column("provider_metadata", sa.JSON(), nullable=True))
    add_if_missing(sa.Column("thyrocare_lead_id", sa.String(length=255), nullable=True))
    add_if_missing(sa.Column("thyrocare_sku_id", sa.String(length=255), nullable=True))
    add_if_missing(sa.Column("thyrocare_order_id", sa.String(length=100), nullable=True))
    add_if_missing(sa.Column("thyrocare_product_id", sa.Integer(), nullable=True))
    add_if_missing(sa.Column("thyrocare_booking_status", sa.String(length=20), nullable=True))
    add_if_missing(sa.Column("thyrocare_booking_error", sa.String(length=500), nullable=True))

    indexes = _indexes()
    if "ix_genetic_order_items_thyrocare_order_id" not in indexes:
        op.create_index(
            "ix_genetic_order_items_thyrocare_order_id",
            TABLE_NAME,
            ["thyrocare_order_id"],
        )
    if "ix_genetic_order_items_thyrocare_booking_status" not in indexes:
        op.create_index(
            "ix_genetic_order_items_thyrocare_booking_status",
            TABLE_NAME,
            ["thyrocare_booking_status"],
        )
