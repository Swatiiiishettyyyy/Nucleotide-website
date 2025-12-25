"""Update order and payment status enums to new values

Revision ID: 036_update_status_enums
Revises: 035_add_cart_table
Create Date: 2025-01-28

Tags: orders, status, enum
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "036_update_status_enums"
down_revision = "035_add_cart_table"
branch_labels = None
depends_on = None


def upgrade():
    """
    Update PaymentStatus and OrderStatus enums to new values.
    Migrate existing data first, then update enum definitions.
    
    PaymentStatus mapping:
    - NOT_INITIATED -> PENDING (order created, payment not started)
    - SUCCESS -> PROCESSING (frontend verified, waiting for webhook)
    - VERIFIED -> COMPLETED (webhook confirmed)
    - FAILED -> FAILED
    
    OrderStatus mapping:
    - CREATED -> PENDING_PAYMENT
    - AWAITING_PAYMENT_CONFIRMATION -> PROCESSING
    - CONFIRMED -> CONFIRMED
    - PAYMENT_FAILED -> PAYMENT_FAILED
    - All other statuses remain the same
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if tables exist
    if 'orders' not in inspector.get_table_names():
        return  # Tables don't exist yet, skip migration
    
    if dialect_name == 'mysql':
        # MySQL: Migrate data first, then update enum
        
        # 1. Migrate payment_status data
        # NOT_INITIATED -> PENDING (order created, payment not started)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'PENDING' 
            WHERE payment_status = 'NOT_INITIATED'
        """))
        
        # SUCCESS -> PROCESSING (frontend verified, waiting for webhook)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'PROCESSING' 
            WHERE payment_status = 'SUCCESS'
        """))
        
        # VERIFIED -> COMPLETED (webhook confirmed payment)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'COMPLETED' 
            WHERE payment_status = 'VERIFIED'
        """))
        
        # FAILED stays as FAILED, no change needed
        
        # 2. Migrate order_status data
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'PENDING_PAYMENT' 
            WHERE order_status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'PROCESSING' 
            WHERE order_status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))
        
        # CONFIRMED, PAYMENT_FAILED, and all other statuses stay the same
        
        # 3. Update payment_status enum
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN payment_status 
            ENUM('NONE', 'PENDING', 'PROCESSING', 'FAILED', 'COMPLETED') 
            NOT NULL DEFAULT 'PENDING'
        """))
        
        # 4. Update order_status enum
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN order_status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'PENDING_PAYMENT'
        """))
        
        # 5. Update order_items.order_status enum
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'PENDING_PAYMENT' 
            WHERE order_status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'PROCESSING' 
            WHERE order_status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_items 
            MODIFY COLUMN order_status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'PENDING_PAYMENT'
        """))
        
        # 6. Update order_status_history.status enum
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'PENDING_PAYMENT' 
            WHERE status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'PROCESSING' 
            WHERE status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN status 
            ENUM('CART', 'PENDING_PAYMENT', 'PROCESSING', 'PAYMENT_FAILED', 'CONFIRMED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL
        """))
        
        # 7. Update order_status_history.previous_status enum (nullable)
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'PENDING_PAYMENT' 
            WHERE previous_status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'PROCESSING' 
            WHERE previous_status = 'AWAITING_PAYMENT_CONFIRMATION'
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
        # PostgreSQL: Add new enum values first, then migrate data
        
        # 1. Add new PaymentStatus enum values
        try:
            connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'NONE'"))
        except Exception:
            pass  # Value might already exist
        
        try:
            connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'PENDING'"))
        except Exception:
            pass
        
        try:
            connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'PROCESSING'"))
        except Exception:
            pass
        
        try:
            connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'COMPLETED'"))
        except Exception:
            pass
        
        # 2. Add new OrderStatus enum values
        try:
            connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'CART'"))
        except Exception:
            pass
        
        try:
            connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'PENDING_PAYMENT'"))
        except Exception:
            pass
        
        try:
            connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'PROCESSING'"))
        except Exception:
            pass
        
        try:
            connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'PAYMENT_FAILED'"))
        except Exception:
            pass
        
        # 3. Migrate payment_status data
        # NOT_INITIATED -> PENDING (order created, payment not started)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'PENDING'::paymentstatus 
            WHERE payment_status = 'NOT_INITIATED'::paymentstatus
        """))
        
        # SUCCESS -> PROCESSING (frontend verified, waiting for webhook)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'PROCESSING'::paymentstatus 
            WHERE payment_status = 'SUCCESS'::paymentstatus
        """))
        
        # VERIFIED -> COMPLETED (webhook confirmed payment)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'COMPLETED'::paymentstatus 
            WHERE payment_status = 'VERIFIED'::paymentstatus
        """))
        
        # 4. Migrate order_status data
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'PENDING_PAYMENT'::orderstatus 
            WHERE order_status = 'CREATED'::orderstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'PROCESSING'::orderstatus 
            WHERE order_status = 'AWAITING_PAYMENT_CONFIRMATION'::orderstatus
        """))
        
        # 5. Update order_items
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'PENDING_PAYMENT'::orderstatus 
            WHERE order_status = 'CREATED'::orderstatus
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'PROCESSING'::orderstatus 
            WHERE order_status = 'AWAITING_PAYMENT_CONFIRMATION'::orderstatus
        """))
        
        # 6. Update order_status_history
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'PENDING_PAYMENT'::orderstatus 
            WHERE status = 'CREATED'::orderstatus
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'PROCESSING'::orderstatus 
            WHERE status = 'AWAITING_PAYMENT_CONFIRMATION'::orderstatus
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'PENDING_PAYMENT'::orderstatus 
            WHERE previous_status = 'CREATED'::orderstatus
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'PROCESSING'::orderstatus 
            WHERE previous_status = 'AWAITING_PAYMENT_CONFIRMATION'::orderstatus
        """))
        
        # Note: PostgreSQL doesn't support removing enum values easily
        # Old values remain but are not used
        
    else:
        # SQLite: SQLite doesn't have native enums, just update the data
        # NOT_INITIATED -> PENDING (order created, payment not started)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'PENDING' 
            WHERE payment_status = 'NOT_INITIATED'
        """))
        
        # SUCCESS -> PROCESSING (frontend verified, waiting for webhook)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'PROCESSING' 
            WHERE payment_status = 'SUCCESS'
        """))
        
        # VERIFIED -> COMPLETED (webhook confirmed payment)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'COMPLETED' 
            WHERE payment_status = 'VERIFIED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'PENDING_PAYMENT' 
            WHERE order_status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'PROCESSING' 
            WHERE order_status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'PENDING_PAYMENT' 
            WHERE order_status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'PROCESSING' 
            WHERE order_status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'PENDING_PAYMENT' 
            WHERE status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'PROCESSING' 
            WHERE status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'PENDING_PAYMENT' 
            WHERE previous_status = 'CREATED'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'PROCESSING' 
            WHERE previous_status = 'AWAITING_PAYMENT_CONFIRMATION'
        """))


def downgrade():
    """
    Revert enum changes.
    Note: This is a basic downgrade - may need manual intervention for MySQL/PostgreSQL.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    if 'orders' not in inspector.get_table_names():
        return
    
    if dialect_name == 'mysql':
        # Revert data migrations first
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'PENDING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'SUCCESS' 
            WHERE payment_status = 'PROCESSING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'VERIFIED' 
            WHERE payment_status = 'COMPLETED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'CREATED' 
            WHERE order_status = 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'AWAITING_PAYMENT_CONFIRMATION' 
            WHERE order_status = 'PROCESSING'
        """))
        
        # Revert enum definitions (simplified - may need manual intervention)
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN payment_status 
            ENUM('NOT_INITIATED', 'SUCCESS', 'VERIFIED', 'FAILED') 
            NOT NULL DEFAULT 'NOT_INITIATED'
        """))
        
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN order_status 
            ENUM('CREATED', 'AWAITING_PAYMENT_CONFIRMATION', 'CONFIRMED', 'PAYMENT_FAILED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'CREATED'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_items 
            MODIFY COLUMN order_status 
            ENUM('CREATED', 'AWAITING_PAYMENT_CONFIRMATION', 'CONFIRMED', 'PAYMENT_FAILED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL DEFAULT 'CREATED'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN status 
            ENUM('CREATED', 'AWAITING_PAYMENT_CONFIRMATION', 'CONFIRMED', 'PAYMENT_FAILED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NOT NULL
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN previous_status 
            ENUM('CREATED', 'AWAITING_PAYMENT_CONFIRMATION', 'CONFIRMED', 'PAYMENT_FAILED',
                 'SCHEDULED', 'SCHEDULE_CONFIRMED_BY_LAB', 'SAMPLE_COLLECTED', 
                 'SAMPLE_RECEIVED_BY_LAB', 'TESTING_IN_PROGRESS', 'REPORT_READY') 
            NULL
        """))
    
    elif dialect_name == 'postgresql':
        # Revert data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED'::paymentstatus 
            WHERE payment_status = 'PENDING'::paymentstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'SUCCESS'::paymentstatus 
            WHERE payment_status = 'PROCESSING'::paymentstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'VERIFIED'::paymentstatus 
            WHERE payment_status = 'COMPLETED'::paymentstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'CREATED'::orderstatus 
            WHERE order_status = 'PENDING_PAYMENT'::orderstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'AWAITING_PAYMENT_CONFIRMATION'::orderstatus 
            WHERE order_status = 'PROCESSING'::orderstatus
        """))
        
        # Note: PostgreSQL enum value removal requires recreating the type
        # This is complex and may not be fully reversible
    
    else:
        # SQLite: Revert data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'PENDING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'SUCCESS' 
            WHERE payment_status = 'PROCESSING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'VERIFIED' 
            WHERE payment_status = 'COMPLETED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'CREATED' 
            WHERE order_status = 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'AWAITING_PAYMENT_CONFIRMATION' 
            WHERE order_status = 'PROCESSING'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'CREATED' 
            WHERE order_status = 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'AWAITING_PAYMENT_CONFIRMATION' 
            WHERE order_status = 'PROCESSING'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'CREATED' 
            WHERE status = 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'AWAITING_PAYMENT_CONFIRMATION' 
            WHERE status = 'PROCESSING'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'CREATED' 
            WHERE previous_status = 'PENDING_PAYMENT'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'AWAITING_PAYMENT_CONFIRMATION' 
            WHERE previous_status = 'PROCESSING'
        """))

