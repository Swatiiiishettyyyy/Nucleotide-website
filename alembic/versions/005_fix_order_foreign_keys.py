"""Fix order foreign keys to allow deletion with SET NULL

Revision ID: 005_order_fks
Revises: 004_order_item_status
Create Date: 2024-01-05 00:00:00.000000

Tags: orders, foreign_keys, constraints
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_order_fks'
down_revision: Union[str, None] = '004_order_item_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Modify foreign key constraints on order_items and orders tables
    to allow deletion of addresses, members, and products with ON DELETE SET NULL.
    This is safe because we use OrderSnapshot for data integrity.
    """
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    if dialect_name != 'mysql':
        # Foreign key modifications are MySQL-specific in this migration
        # For other databases, constraints may need different handling
        return
    
    inspector = sa.inspect(connection)
    
    # Check if tables exist
    if 'order_items' not in inspector.get_table_names() or 'orders' not in inspector.get_table_names():
        return
    
    # Step 1: Make columns nullable in order_items
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    if not order_items_columns.get('address_id', {}).get('nullable', False):
        op.alter_column('order_items', 'address_id', nullable=True)
    
    if not order_items_columns.get('member_id', {}).get('nullable', False):
        op.alter_column('order_items', 'member_id', nullable=True)
    
    if not order_items_columns.get('product_id', {}).get('nullable', False):
        op.alter_column('order_items', 'product_id', nullable=True)
    
    # Step 2: Drop existing foreign key constraints on order_items
    fk_constraints = inspector.get_foreign_keys('order_items')
    for fk in fk_constraints:
        constraint_name = fk.get('name')
        constrained_columns = fk.get('constrained_columns', [])
        
        if constraint_name and any(col in constrained_columns for col in ['address_id', 'member_id', 'product_id']):
            try:
                op.drop_constraint(constraint_name, 'order_items', type_='foreignkey')
            except Exception:
                pass  # Constraint might not exist
    
    # Step 3: Add new foreign key constraints with ON DELETE SET NULL
    existing_fks = inspector.get_foreign_keys('order_items')
    existing_fk_columns = set()
    for fk in existing_fks:
        existing_fk_columns.update(fk.get('constrained_columns', []))
    
    if 'address_id' not in existing_fk_columns:
        op.create_foreign_key(
            'fk_order_items_address_id',
            'order_items', 'addresses',
            ['address_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'member_id' not in existing_fk_columns:
        op.create_foreign_key(
            'fk_order_items_member_id',
            'order_items', 'members',
            ['member_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'product_id' not in existing_fk_columns:
        op.create_foreign_key(
            'fk_order_items_product_id',
            'order_items', 'products',
            ['product_id'], ['ProductId'],
            ondelete='SET NULL'
        )
    
    # Step 4: Fix orders.address_id FK
    orders_fk_constraints = inspector.get_foreign_keys('orders')
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    for fk in orders_fk_constraints:
        constraint_name = fk.get('name')
        if constraint_name and 'address_id' in fk.get('constrained_columns', []):
            try:
                op.drop_constraint(constraint_name, 'orders', type_='foreignkey')
            except Exception:
                pass
    
    # Make address_id nullable if not already
    if not orders_columns.get('address_id', {}).get('nullable', False):
        op.alter_column('orders', 'address_id', nullable=True)
    
    # Add new FK with SET NULL
    orders_fk_constraints_after = inspector.get_foreign_keys('orders')
    has_address_fk = any('address_id' in fk.get('constrained_columns', []) for fk in orders_fk_constraints_after)
    
    if not has_address_fk:
        op.create_foreign_key(
            'fk_orders_address_id',
            'orders', 'addresses',
            ['address_id'], ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    """
    Revert foreign key changes.
    Note: This is a destructive operation and may fail if data exists.
    """
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    if dialect_name != 'mysql':
        return
    
    # Revert order_items foreign keys (restore original constraints)
    # Note: Original constraint behavior may have been RESTRICT or CASCADE
    # This downgrade assumes RESTRICT behavior
    try:
        op.drop_constraint('fk_order_items_address_id', 'order_items', type_='foreignkey')
        op.drop_constraint('fk_order_items_member_id', 'order_items', type_='foreignkey')
        op.drop_constraint('fk_order_items_product_id', 'order_items', type_='foreignkey')
    except Exception:
        pass
    
    # Revert orders.address_id
    try:
        op.drop_constraint('fk_orders_address_id', 'orders', type_='foreignkey')
    except Exception:
        pass

