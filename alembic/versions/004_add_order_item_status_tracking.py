"""Add per-item status tracking to order_items

Revision ID: 004_order_item_status
Revises: 003_member_fields
Create Date: 2024-01-04 00:00:00.000000

Tags: orders, status_tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '004_order_item_status'
down_revision: Union[str, None] = '003_member_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add order_status and status_updated_at to order_items.
    Add order_item_id to order_status_history for per-item tracking.
    """
    # Add order_status to order_items
    # Use ENUM for MySQL, VARCHAR for others
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    if dialect_name == 'mysql':
        # Check if column already exists
        inspector = sa.inspect(connection)
        order_items_columns = {col['name'] for col in inspector.get_columns('order_items')}
        
        if 'order_status' not in order_items_columns:
            # Get enum values from orders table if it exists
            try:
                result = connection.execute(sa.text("""
                    SELECT COLUMN_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'orders' 
                    AND COLUMN_NAME = 'order_status'
                """))
                enum_row = result.fetchone()
                if enum_row and enum_row[0]:
                    enum_def = enum_row[0]
                    connection.execute(sa.text(f"""
                        ALTER TABLE order_items 
                        ADD COLUMN order_status {enum_def} NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                    """))
                else:
                    # Use default enum values
                    connection.execute(sa.text("""
                        ALTER TABLE order_items 
                        ADD COLUMN order_status ENUM(
                            'ORDER_CONFIRMED',
                            'SCHEDULED',
                            'SCHEDULE_CONFIRMED_BY_LAB',
                            'SAMPLE_COLLECTED',
                            'SAMPLE_RECEIVED_BY_LAB',
                            'TESTING_IN_PROGRESS',
                            'REPORT_READY'
                        ) NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                    """))
            except Exception:
                # Fallback to default enum
                connection.execute(sa.text("""
                    ALTER TABLE order_items 
                    ADD COLUMN order_status ENUM(
                        'ORDER_CONFIRMED',
                        'SCHEDULED',
                        'SCHEDULE_CONFIRMED_BY_LAB',
                        'SAMPLE_COLLECTED',
                        'SAMPLE_RECEIVED_BY_LAB',
                        'TESTING_IN_PROGRESS',
                        'REPORT_READY'
                    ) NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                """))
            
            connection.commit()
            op.create_index(op.f('ix_order_items_order_status'), 'order_items', ['order_status'], unique=False)
    else:
        # For non-MySQL databases, use VARCHAR
        op.add_column('order_items', sa.Column('order_status', sa.String(length=50), nullable=False, server_default='order_confirmed'))
        op.create_index(op.f('ix_order_items_order_status'), 'order_items', ['order_status'], unique=False)
    
    # Add status_updated_at to order_items
    inspector = sa.inspect(connection)
    order_items_columns = {col['name'] for col in inspector.get_columns('order_items')}
    
    if 'status_updated_at' not in order_items_columns:
        if dialect_name == 'mysql':
            op.add_column('order_items', sa.Column('status_updated_at', sa.DateTime(timezone=True), nullable=True))
        else:
            op.add_column('order_items', sa.Column('status_updated_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add order_item_id to order_status_history
    inspector = sa.inspect(connection)
    if 'order_status_history' in inspector.get_table_names():
        history_columns = {col['name'] for col in inspector.get_columns('order_status_history')}
        
        if 'order_item_id' not in history_columns:
            if dialect_name == 'mysql':
                op.add_column('order_status_history', sa.Column('order_item_id', sa.Integer(), nullable=True))
            else:
                op.add_column('order_status_history', sa.Column('order_item_id', sa.Integer(), nullable=True))
            
            op.create_index(op.f('ix_order_status_history_order_item_id'), 'order_status_history', ['order_item_id'], unique=False)
            op.create_foreign_key('fk_order_status_history_order_item_id', 'order_status_history', 'order_items', ['order_item_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Remove order item status tracking"""
    op.drop_constraint('fk_order_status_history_order_item_id', 'order_status_history', type_='foreignkey')
    op.drop_index(op.f('ix_order_status_history_order_item_id'), table_name='order_status_history')
    op.drop_column('order_status_history', 'order_item_id')
    op.drop_index(op.f('ix_order_items_order_status'), table_name='order_items')
    op.drop_column('order_items', 'status_updated_at')
    op.drop_column('order_items', 'order_status')

