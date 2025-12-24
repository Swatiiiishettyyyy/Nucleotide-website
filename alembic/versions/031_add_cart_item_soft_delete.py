"""Add soft delete flag to cart_items table

Revision ID: 031_add_cart_item_soft_delete
Revises: 030_fix_payment_status_enum_case
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "031_add_cart_item_soft_delete"
down_revision = "030_fix_payment_status_enum_case"
branch_labels = None
depends_on = None


def upgrade():
    """
    Add is_deleted column to cart_items table for soft delete functionality.
    Mark existing items with cart_id = NULL as deleted.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if table exists
    if 'cart_items' not in inspector.get_table_names():
        return
    
    cart_items_columns = {col['name'] for col in inspector.get_columns('cart_items')}
    
    # Add is_deleted column if it doesn't exist
    if 'is_deleted' not in cart_items_columns:
        op.add_column('cart_items', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
        op.create_index('ix_cart_items_is_deleted', 'cart_items', ['is_deleted'])
        print("  - Added is_deleted column to cart_items")
    
    # Mark existing items with cart_id = NULL as deleted
    result = connection.execute(text("""
        UPDATE cart_items 
        SET is_deleted = 1 
        WHERE cart_id IS NULL
    """))
    if result.rowcount > 0:
        print(f"  - Marked {result.rowcount} existing items with cart_id = NULL as deleted")
    
    connection.commit()


def downgrade():
    """
    Remove is_deleted column from cart_items table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'cart_items' not in inspector.get_table_names():
        return
    
    cart_items_columns = {col['name'] for col in inspector.get_columns('cart_items')}
    
    # Drop index first
    if 'is_deleted' in cart_items_columns:
        try:
            op.drop_index('ix_cart_items_is_deleted', table_name='cart_items')
        except Exception:
            pass
        
        # Drop column
        op.drop_column('cart_items', 'is_deleted')
        print("  - Removed is_deleted column from cart_items")

