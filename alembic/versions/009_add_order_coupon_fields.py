"""Add coupon fields to orders table

Revision ID: 009_order_coupon
Revises: 008_coupon_system
Create Date: 2024-01-09 00:00:00.000000

Tags: orders, coupons
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009_order_coupon'
down_revision: Union[str, None] = '008_coupon_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add coupon_code and coupon_discount columns to orders table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'orders' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name'] for col in inspector.get_columns('orders')}
    
    # Add coupon_code column if it doesn't exist
    if 'coupon_code' not in orders_columns:
        op.add_column('orders', sa.Column('coupon_code', sa.String(length=50), nullable=True))
        op.create_index(op.f('ix_orders_coupon_code'), 'orders', ['coupon_code'], unique=False)
    
    # Add coupon_discount column if it doesn't exist
    if 'coupon_discount' not in orders_columns:
        op.add_column('orders', sa.Column('coupon_discount', sa.Float(), nullable=False, server_default='0.0'))


def downgrade() -> None:
    """Remove coupon fields from orders table"""
    op.drop_index(op.f('ix_orders_coupon_code'), table_name='orders')
    op.drop_column('orders', 'coupon_discount')
    op.drop_column('orders', 'coupon_code')

