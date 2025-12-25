"""force_fix_payment_method_enum_lowercase

Revision ID: 134caa2fd6db
Revises: 51097632eb4d
Create Date: 2025-12-25 13:33:51.242631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '134caa2fd6db'
down_revision: Union[str, None] = '51097632eb4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Force fix payment_method enum to use lowercase 'razorpay'.
    This migration directly converts the enum regardless of current state.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if payments table exists
    if 'payments' not in inspector.get_table_names():
        return  # Table doesn't exist yet, skip migration
    
    if dialect_name == 'mysql':
        try:
            # Step 1: Convert to VARCHAR temporarily (this works regardless of current enum values)
            connection.execute(sa.text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
            """))
            
            # Step 2: Update any values to lowercase 'razorpay'
            connection.execute(sa.text("""
                UPDATE payments 
                SET payment_method = 'razorpay'
                WHERE payment_method IS NOT NULL
            """))
            
            # Step 3: Convert back to enum with lowercase value
            connection.execute(sa.text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method ENUM('razorpay') NOT NULL
            """))
        except Exception as e:
            # Log error but don't fail - might already be correct
            import logging
            logging.warning(f"Could not alter payment_method enum: {e}")
    elif dialect_name == 'postgresql':
        try:
            # For PostgreSQL, rename the enum value if it exists
            connection.execute(sa.text("""
                DO $$ 
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_enum 
                        WHERE enumlabel = 'RAZORPAY' 
                        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'paymentmethod')
                    ) THEN
                        ALTER TYPE paymentmethod RENAME VALUE 'RAZORPAY' TO 'razorpay';
                    END IF;
                END $$;
            """))
        except Exception as e:
            import logging
            logging.warning(f"Could not alter paymentmethod enum: {e}")


def downgrade() -> None:
    """
    Revert payment_method enum back to uppercase 'RAZORPAY'.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    if 'payments' not in inspector.get_table_names():
        return
    
    if dialect_name == 'mysql':
        try:
            connection.execute(sa.text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
            """))
            connection.execute(sa.text("""
                UPDATE payments 
                SET payment_method = 'RAZORPAY'
                WHERE payment_method IS NOT NULL
            """))
            connection.execute(sa.text("""
                ALTER TABLE payments 
                MODIFY COLUMN payment_method ENUM('RAZORPAY') NOT NULL
            """))
        except Exception as e:
            import logging
            logging.warning(f"Could not revert payment_method enum: {e}")
    elif dialect_name == 'postgresql':
        try:
            connection.execute(sa.text("""
                DO $$ 
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_enum 
                        WHERE enumlabel = 'razorpay' 
                        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'paymentmethod')
                    ) THEN
                        ALTER TYPE paymentmethod RENAME VALUE 'razorpay' TO 'RAZORPAY';
                    END IF;
                END $$;
            """))
        except Exception as e:
            import logging
            logging.warning(f"Could not revert paymentmethod enum: {e}")

