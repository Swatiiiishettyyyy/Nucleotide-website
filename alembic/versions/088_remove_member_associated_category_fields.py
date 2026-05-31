"""Remove member associated category fields

Revision ID: 088_remove_member_associated_category_fields
Revises: 087_sync_website_after_bt
Create Date: 2026-05-24
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa


revision: str = "088_remove_member_associated_category_fields"
down_revision: Union[str, None] = "087_sync_website_after_bt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table_name: str) -> Set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "members" not in inspector.get_table_names():
        return

    member_columns = _columns(inspector, "members")

    if "associated_category_id" in member_columns:
        for fk in inspector.get_foreign_keys("members"):
            if "associated_category_id" in fk.get("constrained_columns", []):
                op.drop_constraint(fk["name"], "members", type_="foreignkey")

        indexes = {index["name"] for index in inspector.get_indexes("members")}
        if "ix_members_associated_category_id" in indexes:
            op.drop_index("ix_members_associated_category_id", table_name="members")

        op.drop_column("members", "associated_category_id")

    if "associated_category" in member_columns:
        indexes = {index["name"] for index in inspector.get_indexes("members")}
        if "ix_members_associated_category" in indexes:
            op.drop_index("ix_members_associated_category", table_name="members")

        op.drop_column("members", "associated_category")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "members" not in inspector.get_table_names():
        return

    member_columns = _columns(inspector, "members")

    if "associated_category" not in member_columns:
        op.add_column("members", sa.Column("associated_category", sa.String(100), nullable=True))
        op.create_index("ix_members_associated_category", "members", ["associated_category"])

    if "associated_category_id" not in member_columns:
        op.add_column("members", sa.Column("associated_category_id", sa.Integer(), nullable=True))
        op.create_index("ix_members_associated_category_id", "members", ["associated_category_id"])
        op.create_foreign_key(
            "fk_members_associated_category_id",
            "members",
            "categories",
            ["associated_category_id"],
            ["id"],
        )
