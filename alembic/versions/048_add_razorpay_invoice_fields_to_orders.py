"""Add Razorpay customer and invoice fields to orders table

Revision ID: 048_add_razorpay_invoice_fields_to_orders
Revises: 047_add_lab_report_tables
Create Date: 2026-02-10

Tags: orders, razorpay, invoices
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic. (32 chars max for version_num in DB)
revision = "048_add_razorpay_invoice_fields_"
down_revision = "047_add_lab_report_tables"
branch_labels = None
depends_on = None


def upgrade():
    """
    Add Razorpay customer and invoice fields to orders table.
    These fields are used to link an order to a Razorpay customer and invoice
    so that invoices can be downloaded or emailed later.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    table_names = inspector.get_table_names()

    # --- Orders table: Razorpay invoice fields ---
    if "orders" not in table_names:
        return

    orders_columns = {col["name"] for col in inspector.get_columns("orders")}

    # Add Razorpay customer/invoice columns if they don't exist
    if "razorpay_customer_id" not in orders_columns:
        op.add_column("orders", sa.Column("razorpay_customer_id", sa.String(length=255), nullable=True))
        op.create_index("ix_orders_razorpay_customer_id", "orders", ["razorpay_customer_id"])

    if "razorpay_invoice_id" not in orders_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_id", sa.String(length=255), nullable=True))
        op.create_index("ix_orders_razorpay_invoice_id", "orders", ["razorpay_invoice_id"])

    if "razorpay_invoice_number" not in orders_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_number", sa.String(length=255), nullable=True))

    if "razorpay_invoice_url" not in orders_columns:
        # Use 500 chars for safety as URLs can be long
        op.add_column("orders", sa.Column("razorpay_invoice_url", sa.String(length=500), nullable=True))

    if "razorpay_invoice_status" not in orders_columns:
        op.add_column("orders", sa.Column("razorpay_invoice_status", sa.String(length=50), nullable=True))
        op.create_index("ix_orders_razorpay_invoice_status", "orders", ["razorpay_invoice_status"])

    # --- Account feedback table: account_feedback_requests ---
    if "account_feedback_requests" not in table_names:
        # Fresh install: create table with all expected columns
        op.create_table(
            "account_feedback_requests",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("member_id", sa.Integer(), nullable=True, index=True),
            sa.Column("member_name", sa.String(length=255), nullable=True),
            sa.Column("current_phone", sa.String(length=50), nullable=True),
            sa.Column("new_phone", sa.String(length=50), nullable=True),
            sa.Column("request_type", sa.String(length=50), nullable=False, index=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

        # Add foreign keys if related tables exist
        if "users" in table_names:
            op.create_foreign_key(
                "fk_account_feedback_requests_user_id",
                "account_feedback_requests",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

        if "members" in table_names:
            op.create_foreign_key(
                "fk_account_feedback_requests_member_id",
                "account_feedback_requests",
                "members",
                ["member_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        # Existing deployments might already have account_feedback_requests
        # without the new current_phone column. Make sure it exists to avoid
        # "Unknown column 'current_phone' in 'field list'" errors.
        feedback_columns = {
            col["name"] for col in inspector.get_columns("account_feedback_requests")
        }

        if "current_phone" not in feedback_columns:
            op.add_column(
                "account_feedback_requests",
                sa.Column("current_phone", sa.String(length=50), nullable=True),
            )
        
        if "new_phone" not in feedback_columns:
            op.add_column(
                "account_feedback_requests",
                sa.Column("new_phone", sa.String(length=50), nullable=True),
            )


def downgrade():
    """
    Remove Razorpay customer and invoice fields from orders table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "orders" not in inspector.get_table_names():
        return

    orders_columns = {col["name"] for col in inspector.get_columns("orders")}

    # Drop indexes first where applicable, then columns
    if "razorpay_customer_id" in orders_columns:
        try:
            op.drop_index("ix_orders_razorpay_customer_id", table_name="orders")
        except Exception:
            pass
        op.drop_column("orders", "razorpay_customer_id")

    if "razorpay_invoice_id" in orders_columns:
        try:
            op.drop_index("ix_orders_razorpay_invoice_id", table_name="orders")
        except Exception:
            pass
        op.drop_column("orders", "razorpay_invoice_id")

    if "razorpay_invoice_number" in orders_columns:
        op.drop_column("orders", "razorpay_invoice_number")

    if "razorpay_invoice_url" in orders_columns:
        op.drop_column("orders", "razorpay_invoice_url")

    if "razorpay_invoice_status" in orders_columns:
        try:
            op.drop_index("ix_orders_razorpay_invoice_status", table_name="orders")
        except Exception:
            pass
        op.drop_column("orders", "razorpay_invoice_status")

    # Drop account_feedback_requests table if it exists
    if "account_feedback_requests" in inspector.get_table_names():
        # Drop FKs first (if present), then table
        try:
            op.drop_constraint(
                "fk_account_feedback_requests_user_id",
                "account_feedback_requests",
                type_="foreignkey",
            )
        except Exception:
            pass

        try:
            op.drop_constraint(
                "fk_account_feedback_requests_member_id",
                "account_feedback_requests",
                type_="foreignkey",
            )
        except Exception:
            pass

        op.drop_table("account_feedback_requests")


