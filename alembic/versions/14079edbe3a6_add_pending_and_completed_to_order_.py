"""add_pending_and_completed_to_order_status_enum

Revision ID: 14079edbe3a6
Revises: 7d4fe36b224e
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '14079edbe3a6'
down_revision: Union[str, None] = '7d4fe36b224e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add PENDING and COMPLETED values to OrderStatus enum.
    These new values are added to support order item status synchronization logic.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if tables exist
    if 'orders' not in inspector.get_table_names():
        return  # Tables don't exist yet, skip migration
    
    if dialect_name == 'mysql':
        # MySQL: Add new enum values to order_status columns
        # Update orders.order_status enum
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN order_status 
            ENUM('CART', 'PENDING', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED', 'COMPLETED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'PENDING_PAYMENT'
        """))
        
        # Update order_items.order_status enum
        connection.execute(text("""
            ALTER TABLE order_items 
            MODIFY COLUMN order_status 
            ENUM('CART', 'PENDING', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED', 'COMPLETED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'PENDING_PAYMENT'
        """))
        
        # Update order_status_history.status enum
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN status 
            ENUM('CART', 'PENDING', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED', 'COMPLETED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL
        """))
        
        # Update order_status_history.previous_status enum (nullable)
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN previous_status 
            ENUM('CART', 'PENDING', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED', 'COMPLETED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NULL
        """))
        
    elif dialect_name == 'postgresql':
        # PostgreSQL: Add new enum values using ALTER TYPE
        try:
            connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'PENDING'"))
        except Exception:
            pass  # Value might already exist
        
        try:
            connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'COMPLETED'"))
        except Exception:
            pass  # Value might already exist
        
    else:
        # SQLite: No enum support, just ensure data consistency
        # SQLite stores as TEXT, so no migration needed
        pass


def downgrade() -> None:
    """
    Remove PENDING and COMPLETED values from OrderStatus enum.
    Note: This may fail if there's existing data using these values.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    if 'orders' not in inspector.get_table_names():
        return
    
    if dialect_name == 'mysql':
        # MySQL: Remove enum values (but keep existing values since we can't easily remove enum values)
        # Note: MySQL doesn't support removing enum values directly
        # We'll revert to the previous enum definition without PENDING and COMPLETED
        # But if data exists with these values, this will fail
        
        # Check if any data uses the new values
        result = connection.execute(text("""
            SELECT COUNT(*) FROM orders WHERE order_status IN ('PENDING', 'COMPLETED')
        """))
        if result.scalar() > 0:
            raise Exception("Cannot downgrade: orders table contains 'PENDING' or 'COMPLETED' status values")
        
        result = connection.execute(text("""
            SELECT COUNT(*) FROM order_items WHERE order_status IN ('PENDING', 'COMPLETED')
        """))
        if result.scalar() > 0:
            raise Exception("Cannot downgrade: order_items table contains 'PENDING' or 'COMPLETED' status values")
        
        # Revert enum definitions
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN order_status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_items 
            MODIFY COLUMN order_status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN previous_status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NULL
        """))
        
    elif dialect_name == 'postgresql':
        # PostgreSQL: Cannot easily remove enum values
        # This would require recreating the enum type, which is complex
        # For safety, we'll just log a warning
        print("Warning: PostgreSQL does not support removing enum values easily.")
        print("Downgrade requires manual intervention to recreate the enum type.")
        
    else:
        # SQLite: No action needed
        pass
