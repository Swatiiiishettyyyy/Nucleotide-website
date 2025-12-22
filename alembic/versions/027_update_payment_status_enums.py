"""Update payment and order status enums

Revision ID: 027_update_payment_status_enums
Revises: 026_add_member_profile_photo_url
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "027_update_payment_status_enums"
down_revision = "026_add_member_profile_photo_url"
branch_labels = None
depends_on = None


def upgrade():
    """
    Update PaymentStatus and OrderStatus enums to remove deprecated values
    and add new values. Migrate existing data first.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if tables exist
    if 'orders' not in inspector.get_table_names():
        return  # Tables don't exist yet, skip migration
    
    if dialect_name == 'mysql':
        # MySQL: Migrate data first, then update enum
        
        # 1. Migrate payment_status data: COMPLETED -> VERIFIED
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'verified' 
            WHERE payment_status = 'completed'
        """))
        
        # 2. Migrate order_status data
        # PENDING_PAYMENT -> CREATED (if payment not verified)
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'created' 
            WHERE order_status = 'pending_payment' 
            AND payment_status NOT IN ('verified', 'failed')
        """))
        
        # ORDER_CONFIRMED -> CONFIRMED
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'confirmed' 
            WHERE order_status = 'order_confirmed'
        """))
        
        # 3. Update payment_status enum - remove COMPLETED and CANCELLED, add new values
        # Note: MySQL doesn't support removing enum values directly, need to recreate
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN payment_status 
            ENUM('not_initiated', 'pending', 'success', 'verified', 'failed') 
            NOT NULL DEFAULT 'not_initiated'
        """))
        
        # 4. Update order_status enum - remove PENDING_PAYMENT and ORDER_CONFIRMED, add new values
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN order_status 
            ENUM('created', 'awaiting_payment_confirmation', 'confirmed', 'payment_failed',
                 'scheduled', 'schedule_confirmed_by_lab', 'sample_collected', 
                 'sample_received_by_lab', 'testing_in_progress', 'report_ready') 
            NOT NULL DEFAULT 'created'
        """))
        
        # 5. Update order_items.order_status enum
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'created' 
            WHERE order_status = 'pending_payment'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'confirmed' 
            WHERE order_status = 'order_confirmed'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_items 
            MODIFY COLUMN order_status 
            ENUM('created', 'awaiting_payment_confirmation', 'confirmed', 'payment_failed',
                 'scheduled', 'schedule_confirmed_by_lab', 'sample_collected', 
                 'sample_received_by_lab', 'testing_in_progress', 'report_ready') 
            NOT NULL DEFAULT 'created'
        """))
        
        # 6. Update order_status_history.status enum
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'created' 
            WHERE status = 'pending_payment'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'confirmed' 
            WHERE status = 'order_confirmed'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN status 
            ENUM('created', 'awaiting_payment_confirmation', 'confirmed', 'payment_failed',
                 'scheduled', 'schedule_confirmed_by_lab', 'sample_collected', 
                 'sample_received_by_lab', 'testing_in_progress', 'report_ready') 
            NOT NULL
        """))
        
        # 7. Update order_status_history.previous_status enum (nullable)
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'created' 
            WHERE previous_status = 'pending_payment'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'confirmed' 
            WHERE previous_status = 'order_confirmed'
        """))
        
        connection.execute(text("""
            ALTER TABLE order_status_history 
            MODIFY COLUMN previous_status 
            ENUM('created', 'awaiting_payment_confirmation', 'confirmed', 'payment_failed',
                 'scheduled', 'schedule_confirmed_by_lab', 'sample_collected', 
                 'sample_received_by_lab', 'testing_in_progress', 'report_ready') 
            NULL
        """))
        
    elif dialect_name == 'postgresql':
        # PostgreSQL: Use ALTER TYPE to add values, then migrate data
        
        # 1. Add new enum values first
        connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'verified'"))
        connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'not_initiated'"))
        connection.execute(text("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'success'"))
        
        connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'created'"))
        connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'awaiting_payment_confirmation'"))
        connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'confirmed'"))
        connection.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'payment_failed'"))
        
        # 2. Migrate data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'verified'::paymentstatus 
            WHERE payment_status = 'completed'::paymentstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'created'::orderstatus 
            WHERE order_status = 'pending_payment'::orderstatus 
            AND payment_status NOT IN ('verified', 'failed')::paymentstatus
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'confirmed'::orderstatus 
            WHERE order_status = 'order_confirmed'::orderstatus
        """))
        
        # Note: PostgreSQL doesn't support removing enum values easily
        # You'd need to recreate the type, but that's complex
        # For now, old values remain but are not used
        
    else:
        # SQLite: SQLite doesn't have native enums, they're stored as strings
        # Just migrate the data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'verified' 
            WHERE payment_status = 'completed'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'created' 
            WHERE order_status = 'pending_payment' 
            AND payment_status NOT IN ('verified', 'failed')
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'confirmed' 
            WHERE order_status = 'order_confirmed'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'created' 
            WHERE order_status = 'pending_payment'
        """))
        
        connection.execute(text("""
            UPDATE order_items 
            SET order_status = 'confirmed' 
            WHERE order_status = 'order_confirmed'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'created' 
            WHERE status = 'pending_payment'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET status = 'confirmed' 
            WHERE status = 'order_confirmed'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'created' 
            WHERE previous_status = 'pending_payment'
        """))
        
        connection.execute(text("""
            UPDATE order_status_history 
            SET previous_status = 'confirmed' 
            WHERE previous_status = 'order_confirmed'
        """))


def downgrade():
    """
    Revert enum changes (note: MySQL doesn't support adding removed enum values easily)
    This is a basic downgrade - may need manual intervention for MySQL
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
            SET payment_status = 'completed' 
            WHERE payment_status = 'verified'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'pending_payment' 
            WHERE order_status = 'created' 
            AND payment_status = 'not_initiated'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'order_confirmed' 
            WHERE order_status = 'confirmed'
        """))
        
        # Revert enum (add back old values)
        # Note: This is simplified - you may need to handle this differently
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN payment_status 
            ENUM('pending', 'completed', 'failed', 'cancelled', 
                 'not_initiated', 'success', 'verified') 
            NOT NULL DEFAULT 'pending'
        """))
        
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN order_status 
            ENUM('order_not_placed', 'pending_payment', 'order_confirmed',
                 'created', 'awaiting_payment_confirmation', 'confirmed', 'payment_failed',
                 'scheduled', 'schedule_confirmed_by_lab', 'sample_collected', 
                 'sample_received_by_lab', 'testing_in_progress', 'report_ready') 
            NOT NULL DEFAULT 'pending_payment'
        """))
    
    elif dialect_name == 'postgresql':
        # Revert data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'completed'::paymentstatus 
            WHERE payment_status = 'verified'::paymentstatus
        """))
        # Note: PostgreSQL enum value removal requires recreating the type
        # This is complex and may not be fully reversible
    
    else:
        # SQLite: Revert data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'completed' 
            WHERE payment_status = 'verified'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'pending_payment' 
            WHERE order_status = 'created'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET order_status = 'order_confirmed' 
            WHERE order_status = 'confirmed'
        """))

