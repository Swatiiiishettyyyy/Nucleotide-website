"""Remove total_price, discount, and subtotal from order_items

Revision ID: 014_remove_order_item_price_fields
Revises: 013_remove_technician_lab_fields
Create Date: 2024-11-27 20:00:00.000000

Tags: order_items, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '014_remove_order_item_price_fields'
down_revision: Union[str, None] = '013_remove_technician_lab_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove total_price, discount, and subtotal columns from order_items table.
    Only unit_price (which stores SpecialPrice) is needed.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'order_items' not in inspector.get_table_names():
        return
    
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    # Drop total_price column
    if 'total_price' in order_items_columns:
        op.drop_column('order_items', 'total_price')
    
    # Drop discount column
    if 'discount' in order_items_columns:
        op.drop_column('order_items', 'discount')
    
    # Drop subtotal column
    if 'subtotal' in order_items_columns:
        op.drop_column('order_items', 'subtotal')


def downgrade() -> None:
    """Revert by adding back the columns (for rollback)"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'order_items' not in inspector.get_table_names():
        return
    
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    # Add back total_price column
    if 'total_price' not in order_items_columns:
        op.add_column('order_items',
                     sa.Column('total_price', sa.Float(), nullable=True))
        # Update with calculated value: unit_price * quantity
        connection.execute(sa.text("""
            UPDATE order_items
            SET total_price = unit_price * quantity
            WHERE total_price IS NULL
        """))
        # Make it not nullable after populating
        op.alter_column('order_items', 'total_price',
                       existing_type=sa.Float(),
                       nullable=False)
    
    # Add back discount column
    if 'discount' not in order_items_columns:
        op.add_column('order_items',
                     sa.Column('discount', sa.Float(), nullable=True, server_default='0.0'))
    
    # Add back subtotal column
    if 'subtotal' not in order_items_columns:
        op.add_column('order_items',
                     sa.Column('subtotal', sa.Float(), nullable=True))
        # Update with calculated value: unit_price * quantity (assuming no discount was applied)
        connection.execute(sa.text("""
            UPDATE order_items
            SET subtotal = unit_price * quantity
            WHERE subtotal IS NULL
        """))
        # Make it not nullable after populating
        op.alter_column('order_items', 'subtotal',
                       existing_type=sa.Float(),
                       nullable=False)

