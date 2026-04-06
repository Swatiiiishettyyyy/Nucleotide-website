"""Add coupon_allowed_users table

Revision ID: 056_add_coupon_allowed_users
Revises: 055_add_coupon_usages_and_plan_types
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "056_add_coupon_allowed_users"
down_revision = "055_add_coupon_usages_and_plan_types"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "coupon_allowed_users" in inspector.get_table_names():
        return  # already exists, skip

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


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "coupon_allowed_users" in inspector.get_table_names():
        op.drop_table("coupon_allowed_users")
