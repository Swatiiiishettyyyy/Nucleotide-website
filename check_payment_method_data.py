"""
Check payment_method enum values in the database.
"""
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from database import engine, SessionLocal
from sqlalchemy import text, inspect
from Orders_module.Order_model import Payment, PaymentMethod
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_payment_method_data():
    """Check payment_method enum values in database."""
    try:
        with engine.connect() as connection:
            # Check database type
            db_url = str(engine.url)
            logger.info(f"Database URL: {db_url[:50]}...")
            
            # Check if payments table exists
            inspector = inspect(engine)
            if 'payments' not in inspector.get_table_names():
                logger.error("Payments table does not exist!")
                return
            
            # Get column info
            columns = inspector.get_columns('payments')
            payment_method_col = next((col for col in columns if col['name'] == 'payment_method'), None)
            if payment_method_col:
                logger.info(f"Payment method column type: {payment_method_col['type']}")
                logger.info(f"Payment method column nullable: {payment_method_col['nullable']}")
            
            if 'postgresql' in db_url.lower():
                logger.info("\n=== PostgreSQL Database ===")
                
                # Check enum type definition
                result = connection.execute(text("""
                    SELECT 
                        t.typname as enum_name,
                        e.enumlabel as enum_value
                    FROM pg_type t 
                    JOIN pg_enum e ON t.oid = e.enumtypid 
                    WHERE t.typname = 'paymentmethod'
                    ORDER BY e.enumsortorder;
                """))
                enum_values = result.fetchall()
                logger.info(f"Enum type 'paymentmethod' values: {[v[1] for v in enum_values]}")
                
                # Check actual data values
                result = connection.execute(text("""
                    SELECT 
                        payment_method,
                        payment_method::text as payment_method_text,
                        COUNT(*) as count
                    FROM payments 
                    GROUP BY payment_method, payment_method::text
                    ORDER BY count DESC;
                """))
                data_values = result.fetchall()
                logger.info(f"\nActual data values in payments table:")
                for row in data_values:
                    logger.info(f"  {row[0]} (text: {row[1]}) - Count: {row[2]}")
                
                # Check for any lowercase values
                result = connection.execute(text("""
                    SELECT COUNT(*) 
                    FROM payments 
                    WHERE payment_method::text = 'razorpay'
                """))
                lowercase_count = result.scalar()
                logger.info(f"\nLowercase 'razorpay' count: {lowercase_count}")
                
                # Try to query using SQLAlchemy
                logger.info("\n=== Testing SQLAlchemy Query ===")
                db = SessionLocal()
                try:
                    # Try to get a payment record
                    payment = db.query(Payment).first()
                    if payment:
                        logger.info(f"First payment ID: {payment.id}")
                        logger.info(f"Payment method (raw): {payment.payment_method}")
                        logger.info(f"Payment method (type): {type(payment.payment_method)}")
                        if hasattr(payment.payment_method, 'value'):
                            logger.info(f"Payment method (value): {payment.payment_method.value}")
                    else:
                        logger.info("No payments found in database")
                except Exception as e:
                    logger.error(f"Error querying with SQLAlchemy: {e}", exc_info=True)
                finally:
                    db.close()
                    
            elif 'mysql' in db_url.lower():
                logger.info("\n=== MySQL Database ===")
                
                # Check enum column definition
                result = connection.execute(text("""
                    SELECT COLUMN_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'payments' 
                    AND COLUMN_NAME = 'payment_method'
                """))
                enum_def = result.fetchone()
                if enum_def:
                    logger.info(f"Enum definition: {enum_def[0]}")
                
                # Check actual data values
                result = connection.execute(text("""
                    SELECT 
                        payment_method,
                        COUNT(*) as count
                    FROM payments 
                    GROUP BY payment_method
                    ORDER BY count DESC;
                """))
                data_values = result.fetchall()
                logger.info(f"\nActual data values in payments table:")
                for row in data_values:
                    logger.info(f"  '{row[0]}' - Count: {row[1]}")
                
                # Check for any lowercase values
                result = connection.execute(text("""
                    SELECT COUNT(*) 
                    FROM payments 
                    WHERE payment_method = 'razorpay'
                """))
                lowercase_count = result.scalar()
                logger.info(f"\nLowercase 'razorpay' count: {lowercase_count}")
                
                # Try to query using SQLAlchemy
                logger.info("\n=== Testing SQLAlchemy Query ===")
                db = SessionLocal()
                try:
                    # Try to get a payment record
                    payment = db.query(Payment).first()
                    if payment:
                        logger.info(f"First payment ID: {payment.id}")
                        logger.info(f"Payment method (raw): {payment.payment_method}")
                        logger.info(f"Payment method (type): {type(payment.payment_method)}")
                        if hasattr(payment.payment_method, 'value'):
                            logger.info(f"Payment method (value): {payment.payment_method.value}")
                    else:
                        logger.info("No payments found in database")
                except Exception as e:
                    logger.error(f"Error querying with SQLAlchemy: {e}", exc_info=True)
                finally:
                    db.close()
            else:
                logger.warning(f"Unsupported database type: {db_url}")
                
    except Exception as e:
        logger.error(f"Error checking payment_method data: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("Checking payment_method enum data...")
    check_payment_method_data()
    logger.info("\nDone!")

