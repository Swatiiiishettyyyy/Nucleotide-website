"""fix_payment_method_enum_case

Revision ID: 51097632eb4d
Revises: 6034d26688e2
Create Date: 2025-12-25 13:23:04.683667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51097632eb4d'
down_revision: Union[str, None] = '6034d26688e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix payment_method enum case mismatch.
    Database enum has 'RAZORPAY' (uppercase) but code uses 'razorpay' (lowercase).
    This migration converts the enum to use lowercase 'razorpay' to match the Python enum value.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if payments table exists
    if 'payments' not in inspector.get_table_names():
        return  # Table doesn't exist yet, skip migration
    
    if dialect_name == 'mysql':
        # MySQL: Need to alter the column to change enum values
        # Step 1: Check current enum values
        try:
            result = connection.execute(sa.text("""
                SELECT COLUMN_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'payments' 
                AND COLUMN_NAME = 'payment_method'
            """))
            enum_row = result.fetchone()
            
            if enum_row and enum_row[0]:
                enum_def = enum_row[0]
                # Check if enum has uppercase RAZORPAY (case-insensitive check)
                # MySQL enum definitions look like: ENUM('RAZORPAY') or enum('razorpay')
                enum_def_upper = enum_def.upper()
                has_uppercase = "'RAZORPAY'" in enum_def_upper or "RAZORPAY" in enum_def_upper
                has_lowercase = "'razorpay'" in enum_def.lower()
                
                # If enum has uppercase but not lowercase, fix it
                if has_uppercase and not has_lowercase:
                    # Step 2: Convert to VARCHAR temporarily
                    connection.execute(sa.text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
                    """))
                    
                    # Step 3: Update any uppercase values to lowercase
                    connection.execute(sa.text("""
                        UPDATE payments 
                        SET payment_method = LOWER(payment_method)
                        WHERE UPPER(payment_method) = 'RAZORPAY'
                    """))
                    
                    # Step 4: Convert back to enum with lowercase value
                    connection.execute(sa.text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method ENUM('razorpay') NOT NULL
                    """))
                elif not has_lowercase:
                    # If enum doesn't have lowercase at all, force fix it
                    # This handles edge cases where enum might be in different format
                    connection.execute(sa.text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
                    """))
                    connection.execute(sa.text("""
                        UPDATE payments 
                        SET payment_method = 'razorpay'
                        WHERE payment_method IS NOT NULL
                    """))
                    connection.execute(sa.text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method ENUM('razorpay') NOT NULL
                    """))
        except Exception as e:
            # If enum is already correct or doesn't exist, skip
            print(f"Note: Could not alter payment_method enum: {e}")
    elif dialect_name == 'postgresql':
        # PostgreSQL: Can alter enum type directly
        try:
            # Check if enum type exists with uppercase
            result = connection.execute(sa.text("""
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
                # Rename enum value from RAZORPAY to razorpay
                connection.execute(sa.text("""
                    ALTER TYPE paymentmethod RENAME VALUE 'RAZORPAY' TO 'razorpay'
                """))
        except Exception as e:
            print(f"Note: Could not alter paymentmethod enum: {e}")


def downgrade() -> None:
    """
    Revert payment_method enum back to uppercase 'RAZORPAY'.
    Note: This may cause issues if data uses lowercase 'razorpay'.
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
            connection.execute(sa.text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
            """))
            
            # Update lowercase to uppercase
            connection.execute(sa.text("""
                UPDATE payments 
                SET payment_method = UPPER(payment_method)
                WHERE payment_method = 'razorpay'
            """))
            
            # Convert back to enum with uppercase value
            connection.execute(sa.text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method ENUM('RAZORPAY') NOT NULL
            """))
        except Exception as e:
            print(f"Note: Could not revert payment_method enum: {e}")
    elif dialect_name == 'postgresql':
        try:
            # Rename enum value from razorpay to RAZORPAY
            connection.execute(sa.text("""
                ALTER TYPE paymentmethod RENAME VALUE 'razorpay' TO 'RAZORPAY'
            """))
        except Exception as e:
            print(f"Note: Could not revert paymentmethod enum: {e}")

