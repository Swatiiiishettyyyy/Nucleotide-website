"""Add placed_by_member_id to orders table

Revision ID: 034_add_placed_by_member_id
Revises: 033_remove_member_transfer_system
Create Date: 2025-01-27

Tags: orders, members
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "034_add_placed_by_member_id"
down_revision = "033_remove_member_transfer_system"
branch_labels = None
depends_on = None


def upgrade():
    """
    Add placed_by_member_id column to orders table.
    This tracks which member profile was active when the order was placed.
    Allows members to see orders they placed even if they're not in the order group.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if table exists
    if 'orders' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name'] for col in inspector.get_columns('orders')}
    
    # Add placed_by_member_id column if it doesn't exist
    if 'placed_by_member_id' not in orders_columns:
        op.add_column('orders', sa.Column('placed_by_member_id', sa.Integer(), nullable=True))
        
        # Add foreign key constraint (ON DELETE SET NULL to handle member deletion gracefully)
        # Check if members table exists
        if 'members' in inspector.get_table_names():
            if dialect_name == 'mysql':
                # MySQL specific foreign key syntax
                op.create_foreign_key(
                    'fk_orders_placed_by_member_id',
                    'orders', 'members',
                    ['placed_by_member_id'], ['id'],
                    ondelete='SET NULL'
                )
            else:
                # Generic foreign key for other databases
                op.create_foreign_key(
                    'fk_orders_placed_by_member_id',
                    'orders', 'members',
                    ['placed_by_member_id'], ['id'],
                    ondelete='SET NULL'
                )
        
        # Create index for efficient lookups
        op.create_index('ix_orders_placed_by_member_id', 'orders', ['placed_by_member_id'])
        print("  - Added placed_by_member_id column to orders table with foreign key and index")


def downgrade():
    """
    Remove placed_by_member_id column from orders table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'orders' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name'] for col in inspector.get_columns('orders')}
    
    # Drop index first
    if 'placed_by_member_id' in orders_columns:
        try:
            op.drop_index('ix_orders_placed_by_member_id', table_name='orders')
        except Exception:
            pass
        
        # Drop foreign key constraint
        try:
            op.drop_constraint('fk_orders_placed_by_member_id', 'orders', type_='foreignkey')
        except Exception:
            pass
        
        # Drop column
        op.drop_column('orders', 'placed_by_member_id')
        print("  - Removed placed_by_member_id column from orders table")

