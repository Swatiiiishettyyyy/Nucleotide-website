"""ensure_payment_method_enum_uppercase

Revision ID: 7d4fe36b224e
Revises: 134caa2fd6db
Create Date: 2025-12-25 13:43:24.800903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '7d4fe36b224e'
down_revision: Union[str, None] = '134caa2fd6db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ensure payment_method enum uses uppercase 'RAZORPAY' to match Python enum.
    This migration ensures the database enum matches the code: PaymentMethod.RAZORPAY = "RAZORPAY"
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if payments table exists
    if 'payments' not in inspector.get_table_names():
        return  # Table doesn't exist yet, skip migration
    
    if dialect_name == 'mysql':
        # MySQL: Need to alter the column to ensure enum uses uppercase
        try:
            # Step 1: Check if there's any data with lowercase values
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM payments 
                WHERE payment_method = 'razorpay'
            """))
            lowercase_count = result.scalar()
            
            # Step 2: Check current enum definition
            result = connection.execute(text("""
                SELECT COLUMN_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'payments' 
                AND COLUMN_NAME = 'payment_method'
            """))
            enum_row = result.fetchone()
            
            if enum_row and enum_row[0]:
                enum_def = enum_row[0].upper()
                # Check if enum has lowercase 'razorpay' (case-insensitive check)
                has_lowercase_enum = "'razorpay'" in enum_row[0].lower() and "'RAZORPAY'" not in enum_def
                has_uppercase_enum = "'RAZORPAY'" in enum_def
                
                # If we have lowercase data OR lowercase enum, fix it
                if lowercase_count > 0 or has_lowercase_enum:
                    # Step 3: Convert to VARCHAR temporarily
                    connection.execute(text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
                    """))
                    
                    # Step 4: Update any lowercase values to uppercase
                    connection.execute(text("""
                        UPDATE payments 
                        SET payment_method = 'RAZORPAY'
                        WHERE LOWER(payment_method) = 'razorpay' OR payment_method = 'razorpay'
                    """))
                    
                    # Step 5: Convert back to enum with uppercase value
                    connection.execute(text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method ENUM('RAZORPAY') NOT NULL
                    """))
                # If enum already has uppercase and no lowercase data, do nothing (idempotent)
        except Exception as e:
            # If enum is already correct or doesn't exist, skip
            print(f"Note: Could not alter payment_method enum: {e}")
    elif dialect_name == 'postgresql':
        # PostgreSQL: Update data first, then handle enum type
        try:
            # Step 1: Check if enum type has lowercase value
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = 'paymentmethod' 
                    AND EXISTS (
                        SELECT 1 FROM pg_enum 
                        WHERE enumtypid = pg_type.oid 
                        AND enumlabel = 'razorpay'
                    )
                )
            """))
            has_lowercase_enum = result.scalar()
            
            # Step 2: If enum has lowercase value, rename it (this automatically updates all data)
            if has_lowercase_enum:
                # Rename enum value from razorpay to RAZORPAY (this updates all existing data)
                connection.execute(text("""
                    ALTER TYPE paymentmethod RENAME VALUE 'razorpay' TO 'RAZORPAY'
                """))
            else:
                # Enum type is already uppercase, but data might still have lowercase values
                # This can happen if data was inserted with lowercase before enum was changed
                # We need to update the data by casting to text, updating, then casting back
                # First check if we have any lowercase data
                result = connection.execute(text("""
                    SELECT COUNT(*) 
                    FROM payments 
                    WHERE payment_method::text = 'razorpay'
                """))
                lowercase_count = result.scalar()
                
                if lowercase_count > 0:
                    # Temporarily convert column to text to update values
                    connection.execute(text("""
                        ALTER TABLE payments 
                        ALTER COLUMN payment_method TYPE text
                    """))
                    
                    # Update lowercase values to uppercase
                    connection.execute(text("""
                        UPDATE payments 
                        SET payment_method = 'RAZORPAY'
                        WHERE payment_method = 'razorpay'
                    """))
                    
                    # Convert back to enum type
                    connection.execute(text("""
                        ALTER TABLE payments 
                        ALTER COLUMN payment_method TYPE paymentmethod 
                        USING payment_method::paymentmethod
                    """))
        except Exception as e:
            # If enum value doesn't exist or is already uppercase, skip (idempotent)
            print(f"Note: Could not alter paymentmethod enum: {e}")


def downgrade() -> None:
    """
    Revert payment_method enum back to lowercase 'razorpay'.
    Note: This may cause issues if code expects uppercase 'RAZORPAY'.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if payments table exists
    if 'payments' not in inspector.get_table_names():
        return  # Table doesn't exist, skip migration
    
    if dialect_name == 'mysql':
        try:
            # Convert to VARCHAR temporarily
            connection.execute(text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
            """))
            
            # Update uppercase to lowercase
            connection.execute(text("""
                UPDATE payments 
                SET payment_method = LOWER(payment_method)
                WHERE UPPER(payment_method) = 'RAZORPAY'
            """))
            
            # Convert back to enum with lowercase value
            connection.execute(text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method ENUM('razorpay') NOT NULL
            """))
        except Exception as e:
            print(f"Note: Could not revert payment_method enum: {e}")
    elif dialect_name == 'postgresql':
        try:
            # Check if enum has uppercase value
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = 'paymentmethod' 
                    AND EXISTS (
                        SELECT 1 FROM pg_enum 
                        WHERE enumtypid = pg_type.oid 
                        AND enumlabel = 'RAZORPAY'
                    )
                )
            """))
            has_uppercase = result.scalar()
            
            if has_uppercase:
                # Rename enum value from RAZORPAY to razorpay (this updates all existing data)
                connection.execute(text("""
                    ALTER TYPE paymentmethod RENAME VALUE 'RAZORPAY' TO 'razorpay'
                """))
        except Exception as e:
            print(f"Note: Could not revert paymentmethod enum: {e}")

