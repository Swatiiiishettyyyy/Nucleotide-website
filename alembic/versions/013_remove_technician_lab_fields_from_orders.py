"""Remove technician and lab fields from orders table

Revision ID: 013_remove_technician_lab_fields
Revises: 012_order_fields_nullable
Create Date: 2024-11-27 19:00:00.000000

Tags: orders, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '013_remove_technician_lab_fields'
down_revision: Union[str, None] = '012_order_fields_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Move technician_name, technician_contact, and scheduled_date from orders table
    to order_items table. Remove lab_name from orders (not needed).
    
    This allows each order item to have its own technician and schedule,
    since items can have different addresses.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'orders' not in inspector.get_table_names():
        return
    if 'order_items' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    # Step 1: Add new columns to order_items table if they don't exist
    if 'scheduled_date' not in order_items_columns:
        op.add_column('order_items',
                     sa.Column('scheduled_date', sa.DateTime(timezone=True), nullable=True))
    
    if 'technician_name' not in order_items_columns:
        op.add_column('order_items',
                     sa.Column('technician_name', sa.String(100), nullable=True))
    
    if 'technician_contact' not in order_items_columns:
        op.add_column('order_items',
                     sa.Column('technician_contact', sa.String(20), nullable=True))
    
    # Step 2: Migrate data from orders to order_items (if fields exist in orders)
    # Copy technician and scheduling data from order to all its items
    if 'scheduled_date' in orders_columns or 'technician_name' in orders_columns or 'technician_contact' in orders_columns:
        # Use raw SQL to copy data
        connection.execute(sa.text("""
            UPDATE order_items oi
            INNER JOIN orders o ON oi.order_id = o.id
            SET 
                oi.scheduled_date = COALESCE(oi.scheduled_date, o.scheduled_date),
                oi.technician_name = COALESCE(oi.technician_name, o.technician_name),
                oi.technician_contact = COALESCE(oi.technician_contact, o.technician_contact)
            WHERE o.scheduled_date IS NOT NULL 
               OR o.technician_name IS NOT NULL 
               OR o.technician_contact IS NOT NULL
        """))
    
    # Step 3: Remove columns from orders table if they exist
    if 'scheduled_date' in orders_columns:
        op.drop_column('orders', 'scheduled_date')
    
    if 'technician_name' in orders_columns:
        op.drop_column('orders', 'technician_name')
    
    if 'technician_contact' in orders_columns:
        op.drop_column('orders', 'technician_contact')
    
    # Step 4: Remove lab_name from orders table if it exists (not needed)
    if 'lab_name' in orders_columns:
        op.drop_column('orders', 'lab_name')


def downgrade() -> None:
    """Revert: move fields back to orders table"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'orders' not in inspector.get_table_names():
        return
    if 'order_items' not in inspector.get_table_names():
        return
    
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    # Step 1: Add columns back to orders table
    if 'scheduled_date' not in orders_columns:
        op.add_column('orders',
                     sa.Column('scheduled_date', sa.DateTime(timezone=True), nullable=True))
    
    if 'technician_name' not in orders_columns:
        op.add_column('orders',
                     sa.Column('technician_name', sa.String(100), nullable=True))
    
    if 'technician_contact' not in orders_columns:
        op.add_column('orders',
                     sa.Column('technician_contact', sa.String(20), nullable=True))
    
    if 'lab_name' not in orders_columns:
        op.add_column('orders',
                     sa.Column('lab_name', sa.String(200), nullable=True))
    
    # Step 2: Migrate data back from order_items to orders
    # Use the first item's data for each order (or aggregate if needed)
    connection.execute(sa.text("""
        UPDATE orders o
        INNER JOIN (
            SELECT order_id,
                   MAX(scheduled_date) as scheduled_date,
                   MAX(technician_name) as technician_name,
                   MAX(technician_contact) as technician_contact
            FROM order_items
            GROUP BY order_id
        ) oi ON o.id = oi.order_id
        SET 
            o.scheduled_date = oi.scheduled_date,
            o.technician_name = oi.technician_name,
            o.technician_contact = oi.technician_contact
    """))
    
    # Step 3: Remove columns from order_items table
    if 'scheduled_date' in order_items_columns:
        op.drop_column('order_items', 'scheduled_date')
    
    if 'technician_name' in order_items_columns:
        op.drop_column('order_items', 'technician_name')
    
    if 'technician_contact' in order_items_columns:
        op.drop_column('order_items', 'technician_contact')

