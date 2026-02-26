"""add enquiry_requests table

Revision ID: 054_add_enquiry_requests
Revises: 053_add_serviceable_locations
Create Date: 2026-02-24

Tags: enquiry, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "054_add_enquiry_requests"
down_revision: Union[str, None] = "053_add_serviceable_locations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "enquiry_requests" not in tables:
        op.create_table(
            "enquiry_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("contact_number", sa.String(length=50), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("number_of_tests", sa.Integer(), nullable=False),
            sa.Column("organization", sa.String(length=255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_enquiry_requests_id"), "enquiry_requests", ["id"], unique=False)
        op.create_index(op.f("ix_enquiry_requests_name"), "enquiry_requests", ["name"], unique=False)
        op.create_index(op.f("ix_enquiry_requests_contact_number"), "enquiry_requests", ["contact_number"], unique=False)
        op.create_index(op.f("ix_enquiry_requests_email"), "enquiry_requests", ["email"], unique=False)
        op.create_index(op.f("ix_enquiry_requests_created_at"), "enquiry_requests", ["created_at"], unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "enquiry_requests" in tables:
        op.drop_index(op.f("ix_enquiry_requests_created_at"), table_name="enquiry_requests")
        op.drop_index(op.f("ix_enquiry_requests_email"), table_name="enquiry_requests")
        op.drop_index(op.f("ix_enquiry_requests_contact_number"), table_name="enquiry_requests")
        op.drop_index(op.f("ix_enquiry_requests_name"), table_name="enquiry_requests")
        op.drop_index(op.f("ix_enquiry_requests_id"), table_name="enquiry_requests")
        op.drop_table("enquiry_requests")
