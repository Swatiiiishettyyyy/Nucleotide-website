"""Make order payment and scheduling fields nullable

Revision ID: 012_order_fields_nullable
Revises: 011_remove_coupon_user_id
Create Date: 2024-11-27 18:30:00.000000

Tags: orders, payments
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012_order_fields_nullable'
down_revision: Union[str, None] = '011_remove_coupon_user_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Make payment and scheduling fields nullable in orders table.
    These fields are only filled after payment completion or scheduling.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'orders' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    # Make razorpay_payment_id nullable
    if 'razorpay_payment_id' in orders_columns and not orders_columns['razorpay_payment_id']['nullable']:
        op.alter_column('orders', 'razorpay_payment_id',
                       existing_type=sa.String(255),
                       nullable=True)
    
    # Make razorpay_signature nullable
    if 'razorpay_signature' in orders_columns and not orders_columns['razorpay_signature']['nullable']:
        op.alter_column('orders', 'razorpay_signature',
                       existing_type=sa.String(255),
                       nullable=True)
    
    # Make payment_date nullable
    if 'payment_date' in orders_columns and not orders_columns['payment_date']['nullable']:
        op.alter_column('orders', 'payment_date',
                       existing_type=sa.DateTime(timezone=True),
                       nullable=True)
    
    # Make coupon_code nullable
    if 'coupon_code' in orders_columns and not orders_columns['coupon_code']['nullable']:
        op.alter_column('orders', 'coupon_code',
                       existing_type=sa.String(50),
                       nullable=True)
    
    # Make scheduled_date nullable
    if 'scheduled_date' in orders_columns and not orders_columns['scheduled_date']['nullable']:
        op.alter_column('orders', 'scheduled_date',
                       existing_type=sa.DateTime(timezone=True),
                       nullable=True)
    
    # Make technician_name nullable
    if 'technician_name' in orders_columns and not orders_columns['technician_name']['nullable']:
        op.alter_column('orders', 'technician_name',
                       existing_type=sa.String(100),
                       nullable=True)
    
    # Make technician_contact nullable
    if 'technician_contact' in orders_columns and not orders_columns['technician_contact']['nullable']:
        op.alter_column('orders', 'technician_contact',
                       existing_type=sa.String(20),
                       nullable=True)
    
    # Make lab_name nullable
    if 'lab_name' in orders_columns and not orders_columns['lab_name']['nullable']:
        op.alter_column('orders', 'lab_name',
                       existing_type=sa.String(200),
                       nullable=True)
    
    # Make notes nullable
    if 'notes' in orders_columns and not orders_columns['notes']['nullable']:
        op.alter_column('orders', 'notes',
                       existing_type=sa.Text(),
                       nullable=True)


def downgrade() -> None:
    """Revert fields back to not nullable (for rollback)"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'orders' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    # Revert razorpay_payment_id to not nullable
    if 'razorpay_payment_id' in orders_columns and orders_columns['razorpay_payment_id']['nullable']:
        op.alter_column('orders', 'razorpay_payment_id',
                       existing_type=sa.String(255),
                       nullable=False,
                       server_default='')
    
    # Revert razorpay_signature to not nullable
    if 'razorpay_signature' in orders_columns and orders_columns['razorpay_signature']['nullable']:
        op.alter_column('orders', 'razorpay_signature',
                       existing_type=sa.String(255),
                       nullable=False,
                       server_default='')
    
    # Revert payment_date to not nullable
    if 'payment_date' in orders_columns and orders_columns['payment_date']['nullable']:
        op.alter_column('orders', 'payment_date',
                       existing_type=sa.DateTime(timezone=True),
                       nullable=False)
    
    # Revert coupon_code to not nullable
    if 'coupon_code' in orders_columns and orders_columns['coupon_code']['nullable']:
        op.alter_column('orders', 'coupon_code',
                       existing_type=sa.String(50),
                       nullable=False,
                       server_default='')
    
    # Revert scheduled_date to not nullable
    if 'scheduled_date' in orders_columns and orders_columns['scheduled_date']['nullable']:
        op.alter_column('orders', 'scheduled_date',
                       existing_type=sa.DateTime(timezone=True),
                       nullable=False)
    
    # Revert technician_name to not nullable
    if 'technician_name' in orders_columns and orders_columns['technician_name']['nullable']:
        op.alter_column('orders', 'technician_name',
                       existing_type=sa.String(100),
                       nullable=False,
                       server_default='')
    
    # Revert technician_contact to not nullable
    if 'technician_contact' in orders_columns and orders_columns['technician_contact']['nullable']:
        op.alter_column('orders', 'technician_contact',
                       existing_type=sa.String(20),
                       nullable=False,
                       server_default='')
    
    # Revert lab_name to not nullable
    if 'lab_name' in orders_columns and orders_columns['lab_name']['nullable']:
        op.alter_column('orders', 'lab_name',
                       existing_type=sa.String(200),
                       nullable=False,
                       server_default='')
    
    # Revert notes to not nullable
    if 'notes' in orders_columns and orders_columns['notes']['nullable']:
        op.alter_column('orders', 'notes',
                       existing_type=sa.Text(),
                       nullable=False,
                       server_default='')

