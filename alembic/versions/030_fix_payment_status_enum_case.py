"""Fix payment status enum case mismatch

Revision ID: 030_fix_payment_status_enum_case
Revises: 029_add_banners_table
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "030_fix_payment_status_enum_case"
down_revision = "029_add_banners_table"
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix payment_status enum case mismatch.
    Update existing data from lowercase to uppercase, then update enum definition.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if tables exist
    if 'orders' not in inspector.get_table_names():
        return  # Tables don't exist yet, skip migration
    
    if dialect_name == 'mysql':
        # MySQL: Migrate data first (lowercase -> uppercase), then update enum
        
        # 1. Update all existing payment_status values to uppercase
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'not_initiated'
        """))
        
        # Convert any pending values to NOT_INITIATED (since PENDING is being removed)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'pending' OR payment_status = 'PENDING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'SUCCESS' 
            WHERE payment_status = 'success'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'VERIFIED' 
            WHERE payment_status = 'verified'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'FAILED' 
            WHERE payment_status = 'failed'
        """))
        
        # 2. Update payment_status enum to use uppercase values (without PENDING)
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN payment_status 
            ENUM('NOT_INITIATED', 'SUCCESS', 'VERIFIED', 'FAILED') 
            NOT NULL DEFAULT 'NOT_INITIATED'
        """))
        
    elif dialect_name == 'postgresql':
        # PostgreSQL: Update data first, then handle enum type
        
        # 1. Update all existing payment_status values to uppercase
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'not_initiated'
        """))
        
        # Convert any pending values to NOT_INITIATED (since PENDING is being removed)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'pending' OR payment_status = 'PENDING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'SUCCESS' 
            WHERE payment_status = 'success'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'VERIFIED' 
            WHERE payment_status = 'verified'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'FAILED' 
            WHERE payment_status = 'failed'
        """))
        
        # Note: PostgreSQL enum type changes require recreating the type
        # This is complex, so for now we'll just update the data
        # The enum type will need to be manually updated if needed
        
    else:
        # SQLite: SQLite doesn't have native enums, just update the data
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'not_initiated'
        """))
        
        # Convert any pending values to NOT_INITIATED (since PENDING is being removed)
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'NOT_INITIATED' 
            WHERE payment_status = 'pending' OR payment_status = 'PENDING'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'SUCCESS' 
            WHERE payment_status = 'success'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'VERIFIED' 
            WHERE payment_status = 'verified'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'FAILED' 
            WHERE payment_status = 'failed'
        """))


def downgrade():
    """
    Revert payment_status enum to lowercase values.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    if 'orders' not in inspector.get_table_names():
        return
    
    if dialect_name == 'mysql':
        # Revert data to lowercase
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'not_initiated' 
            WHERE payment_status = 'NOT_INITIATED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'success' 
            WHERE payment_status = 'SUCCESS'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'verified' 
            WHERE payment_status = 'VERIFIED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'failed' 
            WHERE payment_status = 'FAILED'
        """))
        
        # Revert enum to lowercase (without pending)
        connection.execute(text("""
            ALTER TABLE orders 
            MODIFY COLUMN payment_status 
            ENUM('not_initiated', 'success', 'verified', 'failed') 
            NOT NULL DEFAULT 'not_initiated'
        """))
    
    elif dialect_name == 'postgresql':
        # Revert data to lowercase
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'not_initiated' 
            WHERE payment_status = 'NOT_INITIATED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'success' 
            WHERE payment_status = 'SUCCESS'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'verified' 
            WHERE payment_status = 'VERIFIED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'failed' 
            WHERE payment_status = 'FAILED'
        """))
    
    else:
        # SQLite: Revert data to lowercase
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'not_initiated' 
            WHERE payment_status = 'NOT_INITIATED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'success' 
            WHERE payment_status = 'SUCCESS'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'verified' 
            WHERE payment_status = 'VERIFIED'
        """))
        
        connection.execute(text("""
            UPDATE orders 
            SET payment_status = 'failed' 
            WHERE payment_status = 'FAILED'
        """))

