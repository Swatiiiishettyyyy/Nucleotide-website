"""Add coupon system with coupons and cart_coupons tables

Revision ID: 008_coupon_system
Revises: 007_device_sessions
Create Date: 2024-01-08 00:00:00.000000

Tags: cart, coupons, discounts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '008_coupon_system'
down_revision: Union[str, None] = '007_device_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create coupons and cart_coupons tables.
    Add coupon_code column to cart_items.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Create coupons table
    if 'coupons' not in inspector.get_table_names():
        # Handle enum types based on database dialect
        if dialect_name == 'mysql':
            discount_type_col = sa.Column('discount_type', sa.Enum('percentage', 'fixed', name='coupontype'), nullable=False)
            status_col = sa.Column('status', sa.Enum('active', 'inactive', 'expired', name='couponstatus'), nullable=False)
        else:
            # For PostgreSQL, SQLite, etc. use VARCHAR
            discount_type_col = sa.Column('discount_type', sa.String(length=20), nullable=False)
            status_col = sa.Column('status', sa.String(length=20), nullable=False)
        
        op.create_table(
            'coupons',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('coupon_code', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=500), nullable=True),
            discount_type_col,
            sa.Column('discount_value', sa.Float(), nullable=False),
            sa.Column('min_order_amount', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('max_discount_amount', sa.Float(), nullable=True),
            sa.Column('max_uses', sa.Integer(), nullable=True),
            sa.Column('max_uses_per_user', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
            sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
            status_col,
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('coupon_code')
        )
        op.create_index(op.f('ix_coupons_id'), 'coupons', ['id'], unique=False)
        op.create_index(op.f('ix_coupons_coupon_code'), 'coupons', ['coupon_code'], unique=True)
        op.create_index(op.f('ix_coupons_status'), 'coupons', ['status'], unique=False)
    
    # Create cart_coupons table
    if 'cart_coupons' not in inspector.get_table_names():
        op.create_table(
            'cart_coupons',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('coupon_id', sa.Integer(), nullable=False),
            sa.Column('coupon_code', sa.String(length=50), nullable=False),
            sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_cart_coupons_id'), 'cart_coupons', ['id'], unique=False)
        op.create_index(op.f('ix_cart_coupons_user_id'), 'cart_coupons', ['user_id'], unique=False)
        op.create_index(op.f('ix_cart_coupons_coupon_id'), 'cart_coupons', ['coupon_id'], unique=False)
        op.create_index(op.f('ix_cart_coupons_coupon_code'), 'cart_coupons', ['coupon_code'], unique=False)
        op.create_foreign_key('fk_cart_coupons_coupon_id', 'cart_coupons', 'coupons', ['coupon_id'], ['id'], ondelete='CASCADE')
    
    # Add coupon_code to cart_items
    if 'cart_items' in inspector.get_table_names():
        cart_items_columns = {col['name'] for col in inspector.get_columns('cart_items')}
        
        if 'coupon_code' not in cart_items_columns:
            op.add_column('cart_items', sa.Column('coupon_code', sa.String(length=50), nullable=True))
            op.create_index(op.f('ix_cart_items_coupon_code'), 'cart_items', ['coupon_code'], unique=False)


def downgrade() -> None:
    """Remove coupon system"""
    op.drop_index(op.f('ix_cart_items_coupon_code'), table_name='cart_items')
    op.drop_column('cart_items', 'coupon_code')
    op.drop_index(op.f('ix_cart_coupons_coupon_code'), table_name='cart_coupons')
    op.drop_index(op.f('ix_cart_coupons_coupon_id'), table_name='cart_coupons')
    op.drop_index(op.f('ix_cart_coupons_user_id'), table_name='cart_coupons')
    op.drop_index(op.f('ix_cart_coupons_id'), table_name='cart_coupons')
    op.drop_table('cart_coupons')
    op.drop_index(op.f('ix_coupons_status'), table_name='coupons')
    op.drop_index(op.f('ix_coupons_coupon_code'), table_name='coupons')
    op.drop_index(op.f('ix_coupons_id'), table_name='coupons')
    op.drop_table('coupons')

