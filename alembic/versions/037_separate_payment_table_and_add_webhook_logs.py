"""Separate payment table and add webhook logs

Revision ID: 037_separate_payment_table
Revises: 036_update_status_enums
Create Date: 2025-01-28

Tags: payments, webhooks, refactoring
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "037_separate_payment_table"
down_revision = "036_update_status_enums"
branch_labels = None
depends_on = None


def upgrade():
    """
    Create separate payment table, webhook_logs table, and payment_transitions table.
    Migrate existing payment data from orders table to payments table.
    Remove payment fields from orders table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if tables exist
    if 'orders' not in inspector.get_table_names():
        return  # Tables don't exist yet, skip migration
    
    # Step 1: Create payments table
    if 'payments' not in inspector.get_table_names():
        op.create_table(
            'payments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('payment_method', sa.Enum('razorpay', name='paymentmethod'), nullable=False),
            sa.Column('payment_status', sa.Enum('NONE', 'PENDING', 'PROCESSING', 'FAILED', 'COMPLETED', name='paymentstatus'), nullable=False),
            sa.Column('razorpay_order_id', sa.String(length=255), nullable=False),
            sa.Column('razorpay_payment_id', sa.String(length=255), nullable=True),
            sa.Column('razorpay_signature', sa.String(length=255), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
            sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes
        op.create_index('ix_payments_order_id', 'payments', ['order_id'])
        op.create_index('ix_payments_payment_status', 'payments', ['payment_status'])
        op.create_index('ix_payments_razorpay_order_id', 'payments', ['razorpay_order_id'])
        op.create_index('ix_payments_razorpay_payment_id', 'payments', ['razorpay_payment_id'], unique=True)
        op.create_index('ix_payments_created_at', 'payments', ['created_at'])
    
    # Step 2: Migrate existing payment data from orders to payments table
    # Get all orders with payment information
    if dialect_name == 'mysql':
        connection.execute(text("""
            INSERT INTO payments (
                order_id, payment_method, payment_status, razorpay_order_id,
                razorpay_payment_id, razorpay_signature, amount, currency,
                payment_date, created_at, updated_at
            )
            SELECT 
                id as order_id,
                payment_method,
                payment_status,
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature,
                total_amount as amount,
                'INR' as currency,
                payment_date,
                created_at,
                updated_at
            FROM orders
            WHERE razorpay_order_id IS NOT NULL
        """))
    elif dialect_name == 'postgresql':
        connection.execute(text("""
            INSERT INTO payments (
                order_id, payment_method, payment_status, razorpay_order_id,
                razorpay_payment_id, razorpay_signature, amount, currency,
                payment_date, created_at, updated_at
            )
            SELECT 
                id as order_id,
                payment_method,
                payment_status,
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature,
                total_amount as amount,
                'INR' as currency,
                payment_date,
                created_at,
                updated_at
            FROM orders
            WHERE razorpay_order_id IS NOT NULL
        """))
    else:
        # SQLite
        connection.execute(text("""
            INSERT INTO payments (
                order_id, payment_method, payment_status, razorpay_order_id,
                razorpay_payment_id, razorpay_signature, amount, currency,
                payment_date, created_at, updated_at
            )
            SELECT 
                id as order_id,
                payment_method,
                payment_status,
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature,
                total_amount as amount,
                'INR' as currency,
                payment_date,
                created_at,
                updated_at
            FROM orders
            WHERE razorpay_order_id IS NOT NULL
        """))
    
    # Step 3: Create webhook_logs table
    if 'webhook_logs' not in inspector.get_table_names():
        op.create_table(
            'webhook_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(length=100), nullable=False),
            sa.Column('event_id', sa.String(length=255), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('processing_error', sa.Text(), nullable=True),
            sa.Column('signature_valid', sa.Boolean(), nullable=True),
            sa.Column('signature_verification_error', sa.Text(), nullable=True),
            sa.Column('order_id', sa.Integer(), nullable=True),
            sa.Column('payment_id', sa.Integer(), nullable=True),
            sa.Column('razorpay_order_id', sa.String(length=255), nullable=True),
            sa.Column('razorpay_payment_id', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('event_id')
        )
        
        # Create indexes
        op.create_index('ix_webhook_logs_event_type', 'webhook_logs', ['event_type'])
        op.create_index('ix_webhook_logs_event_id', 'webhook_logs', ['event_id'], unique=True)
        op.create_index('ix_webhook_logs_processed', 'webhook_logs', ['processed'])
        op.create_index('ix_webhook_logs_order_id', 'webhook_logs', ['order_id'])
        op.create_index('ix_webhook_logs_payment_id', 'webhook_logs', ['payment_id'])
        op.create_index('ix_webhook_logs_razorpay_order_id', 'webhook_logs', ['razorpay_order_id'])
        op.create_index('ix_webhook_logs_razorpay_payment_id', 'webhook_logs', ['razorpay_payment_id'])
        op.create_index('ix_webhook_logs_created_at', 'webhook_logs', ['created_at'])
    
    # Step 4: Create payment_transitions table
    if 'payment_transitions' not in inspector.get_table_names():
        op.create_table(
            'payment_transitions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('payment_id', sa.Integer(), nullable=False),
            sa.Column('from_status', sa.Enum('NONE', 'PENDING', 'PROCESSING', 'FAILED', 'COMPLETED', name='paymentstatus'), nullable=True),
            sa.Column('to_status', sa.Enum('NONE', 'PENDING', 'PROCESSING', 'FAILED', 'COMPLETED', name='paymentstatus'), nullable=False),
            sa.Column('transition_reason', sa.Text(), nullable=True),
            sa.Column('triggered_by', sa.String(length=100), nullable=False, server_default='system'),
            sa.Column('razorpay_event_id', sa.String(length=255), nullable=True),
            sa.Column('webhook_log_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['webhook_log_id'], ['webhook_logs.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes
        op.create_index('ix_payment_transitions_payment_id', 'payment_transitions', ['payment_id'])
        op.create_index('ix_payment_transitions_to_status', 'payment_transitions', ['to_status'])
        op.create_index('ix_payment_transitions_created_at', 'payment_transitions', ['created_at'])
    
    # Step 5: Create initial payment transitions for existing payments
    connection.execute(text("""
        INSERT INTO payment_transitions (
            payment_id, from_status, to_status, transition_reason, triggered_by, created_at
        )
        SELECT 
            id as payment_id,
            NULL as from_status,
            payment_status as to_status,
            'Initial payment status from migration' as transition_reason,
            'system' as triggered_by,
            created_at
        FROM payments
    """))
    
    # Step 6: Remove payment fields from orders table
    # Note: We keep payment_status in orders for backward compatibility and quick queries
    # But actual payment data is now in payments table
    
    # Drop columns from orders table
    try:
        op.drop_column('orders', 'payment_method')
    except Exception:
        pass  # Column might not exist
    
    try:
        op.drop_column('orders', 'razorpay_order_id')
    except Exception:
        pass
    
    try:
        op.drop_column('orders', 'razorpay_payment_id')
    except Exception:
        pass
    
    try:
        op.drop_column('orders', 'razorpay_signature')
    except Exception:
        pass
    
    try:
        op.drop_column('orders', 'payment_date')
    except Exception:
        pass
    
    # Note: We keep payment_status in orders table for quick filtering
    # But it should be synced from the latest payment


def downgrade():
    """
    Revert changes: Add payment fields back to orders table, drop new tables.
    Note: This will lose webhook log and payment transition data.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Step 1: Add payment fields back to orders table
    if 'orders' in inspector.get_table_names():
        # Get payment data from latest payment for each order
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE orders
                ADD COLUMN payment_method ENUM('razorpay') NOT NULL DEFAULT 'razorpay' AFTER coupon_discount,
                ADD COLUMN razorpay_order_id VARCHAR(255) NULL AFTER payment_method,
                ADD COLUMN razorpay_payment_id VARCHAR(255) NULL AFTER razorpay_order_id,
                ADD COLUMN razorpay_signature VARCHAR(255) NULL AFTER razorpay_payment_id,
                ADD COLUMN payment_date DATETIME NULL AFTER razorpay_signature
            """))
            
            # Update orders with latest payment data
            connection.execute(text("""
                UPDATE orders o
                INNER JOIN (
                    SELECT order_id, payment_method, razorpay_order_id, razorpay_payment_id,
                           razorpay_signature, payment_date
                    FROM payments
                    WHERE id IN (
                        SELECT MAX(id) FROM payments GROUP BY order_id
                    )
                ) p ON o.id = p.order_id
                SET o.payment_method = p.payment_method,
                    o.razorpay_order_id = p.razorpay_order_id,
                    o.razorpay_payment_id = p.razorpay_payment_id,
                    o.razorpay_signature = p.razorpay_signature,
                    o.payment_date = p.payment_date
            """))
        elif dialect_name == 'postgresql':
            op.add_column('orders', sa.Column('payment_method', sa.Enum('razorpay', name='paymentmethod'), nullable=False, server_default='razorpay'))
            op.add_column('orders', sa.Column('razorpay_order_id', sa.String(length=255), nullable=True))
            op.add_column('orders', sa.Column('razorpay_payment_id', sa.String(length=255), nullable=True))
            op.add_column('orders', sa.Column('razorpay_signature', sa.String(length=255), nullable=True))
            op.add_column('orders', sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True))
            
            # Update orders with latest payment data
            connection.execute(text("""
                UPDATE orders o
                SET payment_method = p.payment_method,
                    razorpay_order_id = p.razorpay_order_id,
                    razorpay_payment_id = p.razorpay_payment_id,
                    razorpay_signature = p.razorpay_signature,
                    payment_date = p.payment_date
                FROM (
                    SELECT DISTINCT ON (order_id) order_id, payment_method, razorpay_order_id,
                           razorpay_payment_id, razorpay_signature, payment_date
                    FROM payments
                    ORDER BY order_id, id DESC
                ) p
                WHERE o.id = p.order_id
            """))
        else:
            # SQLite
            op.add_column('orders', sa.Column('payment_method', sa.String(), nullable=False, server_default='razorpay'))
            op.add_column('orders', sa.Column('razorpay_order_id', sa.String(length=255), nullable=True))
            op.add_column('orders', sa.Column('razorpay_payment_id', sa.String(length=255), nullable=True))
            op.add_column('orders', sa.Column('razorpay_signature', sa.String(length=255), nullable=True))
            op.add_column('orders', sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True))
            
            # Update orders with latest payment data (SQLite doesn't support UPDATE FROM)
            # This is simplified - may need manual intervention
            pass
    
    # Step 2: Drop new tables
    if 'payment_transitions' in inspector.get_table_names():
        op.drop_table('payment_transitions')
    
    if 'webhook_logs' in inspector.get_table_names():
        op.drop_table('webhook_logs')
    
    if 'payments' in inspector.get_table_names():
        op.drop_table('payments')

