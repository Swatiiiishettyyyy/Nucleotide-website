"""Remove coupon_code column from cart_items table

Revision ID: 010_remove_cart_item_coupon
Revises: 009_order_coupon
Create Date: 2024-11-27 17:40:00.000000

Tags: cart, coupons
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '010_remove_cart_item_coupon'
down_revision: Union[str, None] = '009_order_coupon'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove coupon_code column from cart_items table.
    Coupon tracking is now handled by cart_coupons table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'cart_items' not in inspector.get_table_names():
        return
    
    cart_items_columns = {col['name'] for col in inspector.get_columns('cart_items')}
    
    # Drop coupon_code column if it exists
    if 'coupon_code' in cart_items_columns:
        # Drop index first if it exists
        try:
            op.drop_index('ix_cart_items_coupon_code', table_name='cart_items')
        except Exception:
            # Index might not exist, continue
            pass
        
        # Drop the column
        op.drop_column('cart_items', 'coupon_code')


def downgrade() -> None:
    """Add coupon_code column back to cart_items table (for rollback)"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'cart_items' not in inspector.get_table_names():
        return
    
    cart_items_columns = {col['name'] for col in inspector.get_columns('cart_items')}
    
    # Add coupon_code column back if it doesn't exist
    if 'coupon_code' not in cart_items_columns:
        op.add_column('cart_items', sa.Column('coupon_code', sa.String(length=50), nullable=True))
        op.create_index(op.f('ix_cart_items_coupon_code'), 'cart_items', ['coupon_code'], unique=False)

