"""
Quick fix script to update payment_method values from lowercase to uppercase.
Run this if you're getting enum mismatch errors before running the migration.
"""
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_payment_method_case():
    """Fix payment_method enum case mismatch by updating existing data."""
    try:
        with engine.connect() as connection:
            # Check database type
            db_url = str(engine.url)
            
            if 'postgresql' in db_url.lower():
                logger.info("Detected PostgreSQL database")
                
                # Step 1: Check if there are lowercase values
                result = connection.execute(text("""
                    SELECT COUNT(*) 
                    FROM payments 
                    WHERE payment_method::text = 'razorpay'
                """))
                lowercase_count = result.scalar()
                
                if lowercase_count > 0:
                    logger.info(f"Found {lowercase_count} records with lowercase 'razorpay'")
                    
                    # Convert column to text temporarily
                    logger.info("Converting payment_method column to text...")
                    connection.execute(text("""
                        ALTER TABLE payments 
                        ALTER COLUMN payment_method TYPE text
                    """))
                    connection.commit()
                    
                    # Update lowercase values to uppercase
                    logger.info("Updating lowercase values to uppercase...")
                    result = connection.execute(text("""
                        UPDATE payments 
                        SET payment_method = 'RAZORPAY'
                        WHERE payment_method = 'razorpay'
                    """))
                    connection.commit()
                    logger.info(f"Updated {result.rowcount} records")
                    
                    # Convert back to enum type
                    logger.info("Converting payment_method column back to enum type...")
                    connection.execute(text("""
                        ALTER TABLE payments 
                        ALTER COLUMN payment_method TYPE paymentmethod 
                        USING payment_method::paymentmethod
                    """))
                    connection.commit()
                    logger.info("Successfully fixed payment_method enum case!")
                else:
                    logger.info("No lowercase values found. Data is already correct.")
                    
            elif 'mysql' in db_url.lower():
                logger.info("Detected MySQL database")
                
                # Check if there are lowercase values
                result = connection.execute(text("""
                    SELECT COUNT(*) 
                    FROM payments 
                    WHERE payment_method = 'razorpay'
                """))
                lowercase_count = result.scalar()
                
                if lowercase_count > 0:
                    logger.info(f"Found {lowercase_count} records with lowercase 'razorpay'")
                    
                    # Convert to VARCHAR temporarily
                    logger.info("Converting payment_method column to VARCHAR...")
                    connection.execute(text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method VARCHAR(50) NOT NULL
                    """))
                    connection.commit()
                    
                    # Update lowercase values
                    logger.info("Updating lowercase values to uppercase...")
                    result = connection.execute(text("""
                        UPDATE payments 
                        SET payment_method = 'RAZORPAY'
                        WHERE payment_method = 'razorpay'
                    """))
                    connection.commit()
                    logger.info(f"Updated {result.rowcount} records")
                    
                    # Convert back to enum
                    logger.info("Converting payment_method column back to ENUM...")
                    connection.execute(text("""
                        ALTER TABLE payments 
                        MODIFY COLUMN payment_method ENUM('RAZORPAY') NOT NULL
                    """))
                    connection.commit()
                    logger.info("Successfully fixed payment_method enum case!")
                else:
                    logger.info("No lowercase values found. Data is already correct.")
            else:
                logger.warning(f"Unsupported database type: {db_url}")
                
    except Exception as e:
        logger.error(f"Error fixing payment_method enum case: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("Starting payment_method enum case fix...")
    fix_payment_method_case()
    logger.info("Done!")

