"""add_payment_method_details_to_payments

Revision ID: 6034d26688e2
Revises: 037_separate_payment_table
Create Date: 2025-12-25 13:16:20.179484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6034d26688e2'
down_revision: Union[str, None] = '037_separate_payment_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add payment_method_details and payment_method_metadata columns to payments table.
    These columns store information about how the payment was made (e.g., UPI, card, netbanking).
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if payments table exists
    if 'payments' not in inspector.get_table_names():
        return  # Table doesn't exist yet, skip migration
    
    # Check if columns already exist
    payments_columns = {col['name']: col for col in inspector.get_columns('payments')}
    
    # Add payment_method_details column if it doesn't exist
    if 'payment_method_details' not in payments_columns:
        op.add_column('payments', 
                     sa.Column('payment_method_details', sa.String(length=100), nullable=True))
        # Create index on payment_method_details
        op.create_index('ix_payments_payment_method_details', 'payments', ['payment_method_details'])
    
    # Add payment_method_metadata column if it doesn't exist
    if 'payment_method_metadata' not in payments_columns:
        op.add_column('payments', 
                     sa.Column('payment_method_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    """
    Remove payment_method_details and payment_method_metadata columns from payments table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if payments table exists
    if 'payments' not in inspector.get_table_names():
        return  # Table doesn't exist, skip migration
    
    # Check if columns exist
    payments_columns = {col['name']: col for col in inspector.get_columns('payments')}
    
    # Drop index and column for payment_method_details
    if 'payment_method_details' in payments_columns:
        try:
            op.drop_index('ix_payments_payment_method_details', table_name='payments')
        except Exception:
            pass  # Index might not exist
        op.drop_column('payments', 'payment_method_details')
    
    # Drop column for payment_method_metadata
    if 'payment_method_metadata' in payments_columns:
        op.drop_column('payments', 'payment_method_metadata')

