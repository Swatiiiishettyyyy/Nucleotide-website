"""Repair genetic coupon tables (coupons, coupon_usages, coupon_allowed_users)

Revision ID: 092_repair_genetic_coupon_tables
Revises: 091_repair_cart_coupons_table
Create Date: 2026-05-24
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa


revision: str = "092_repair_genetic_coupon_tables"
down_revision: Union[str, None] = "091_repair_cart_coupons_table"
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


def _foreign_keys(inspector: sa.Inspector, table_name: str) -> Set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    dialect_name = bind.dialect.name

    if "coupons" not in tables:
        if dialect_name == "mysql":
            discount_type_col = sa.Column(
                "discount_type",
                sa.Enum("percentage", "fixed", name="coupontype"),
                nullable=False,
            )
            status_col = sa.Column(
                "status",
                sa.Enum("active", "inactive", "expired", name="couponstatus"),
                nullable=False,
            )
        else:
            discount_type_col = sa.Column("discount_type", sa.String(length=20), nullable=False)
            status_col = sa.Column("status", sa.String(length=20), nullable=False)

        op.create_table(
            "coupons",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("coupon_code", sa.String(length=50), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            discount_type_col,
            sa.Column("discount_value", sa.Float(), nullable=False),
            sa.Column("min_order_amount", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("max_discount_amount", sa.Float(), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("max_uses_per_user", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
            status_col,
            sa.Column("allowed_plan_types", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("coupon_code"),
        )
        op.create_index("ix_coupons_id", "coupons", ["id"], unique=False)
        op.create_index("ix_coupons_coupon_code", "coupons", ["coupon_code"], unique=True)
        op.create_index("ix_coupons_status", "coupons", ["status"], unique=False)
        tables.add("coupons")
    else:
        coupon_columns = _columns(inspector, "coupons")
        if "allowed_plan_types" not in coupon_columns:
            op.add_column("coupons", sa.Column("allowed_plan_types", sa.String(length=255), nullable=True))

    if "coupon_usages" not in tables:
        op.create_table(
            "coupon_usages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("coupon_id", sa.Integer(), nullable=False),
            sa.Column("coupon_code", sa.String(length=50), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("order_number", sa.String(length=50), nullable=False),
            sa.Column("discount_amount", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column(
                "used_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_coupon_usages_coupon_id", "coupon_usages", ["coupon_id"])
        op.create_index("ix_coupon_usages_coupon_code", "coupon_usages", ["coupon_code"])
        op.create_index("ix_coupon_usages_user_id", "coupon_usages", ["user_id"])
        op.create_index("ix_coupon_usages_order_id", "coupon_usages", ["order_id"])
        tables.add("coupon_usages")

    if "coupon_allowed_users" not in tables:
        op.create_table(
            "coupon_allowed_users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("coupon_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("mobile", sa.String(length=100), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user_id"),
            sa.UniqueConstraint("coupon_id", "mobile", name="uq_coupon_mobile"),
            sa.CheckConstraint(
                "user_id IS NOT NULL OR mobile IS NOT NULL",
                name="ck_coupon_allowed_users_not_both_null",
            ),
        )
        op.create_index(
            "ix_coupon_allowed_users_coupon_id",
            "coupon_allowed_users",
            ["coupon_id"],
        )
        op.create_index(
            "ix_coupon_allowed_users_user_id",
            "coupon_allowed_users",
            ["user_id"],
        )
        op.create_index(
            "ix_coupon_allowed_users_mobile",
            "coupon_allowed_users",
            ["mobile"],
        )

    if "cart_coupons" in tables and "coupons" in tables:
        cart_coupon_fks = _foreign_keys(inspector, "cart_coupons")
        if "fk_cart_coupons_coupon_id" not in cart_coupon_fks:
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
