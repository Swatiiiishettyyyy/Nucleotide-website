"""
Test script to specifically create order tables.
Run this to diagnose why order tables aren't being created.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from database import Base, engine
from sqlalchemy import inspect

# Import ONLY order models first
logger.info("="*70)
logger.info("TESTING ORDER TABLE CREATION")
logger.info("="*70)
logger.info("")

logger.info("Step 1: Importing Order models...")
try:
    from Orders_module.Order_model import Order, OrderItem, OrderSnapshot, OrderStatusHistory
    logger.info("✓ Successfully imported Order models")
    logger.info(f"  - Order")
    logger.info(f"  - OrderItem")
    logger.info(f"  - OrderSnapshot")
    logger.info(f"  - OrderStatusHistory")
except Exception as e:
    logger.error(f"❌ Failed to import Order models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("")
logger.info("Step 2: Checking Base.metadata registration...")
order_tables_expected = ['orders', 'order_items', 'order_snapshots', 'order_status_history']
registered_tables = list(Base.metadata.tables.keys())

logger.info(f"Total tables in Base.metadata: {len(registered_tables)}")
logger.info("Registered tables:")
for table_name in sorted(registered_tables):
    logger.info(f"  - {table_name}")

logger.info("")
logger.info("Checking for order tables:")
for table_name in order_tables_expected:
    if table_name in registered_tables:
        logger.info(f"  ✓ {table_name} is registered")
    else:
        logger.error(f"  ✗ {table_name} is NOT registered!")

logger.info("")
logger.info("Step 3: Checking existing tables in database...")
try:
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    logger.info(f"Existing tables in database: {len(existing_tables)}")
    for table_name in sorted(existing_tables):
        logger.info(f"  - {table_name}")
    
    logger.info("")
    logger.info("Checking for order tables in database:")
    for table_name in order_tables_expected:
        if table_name in existing_tables:
            logger.info(f"  ✓ {table_name} exists in database")
        else:
            logger.warning(f"  ✗ {table_name} does NOT exist in database")
except Exception as e:
    logger.error(f"❌ Error checking database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("")
logger.info("Step 4: Attempting to create order tables...")
missing_order_tables = [t for t in order_tables_expected if t not in existing_tables]

if not missing_order_tables:
    logger.info("✅ All order tables already exist!")
    sys.exit(0)

logger.info(f"Missing order tables: {', '.join(missing_order_tables)}")

# Try to create them
try:
    logger.info("Creating tables using Base.metadata.create_all()...")
    
    # Method 1: Direct creation
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("✓ create_all() executed")
    
    # Wait a bit
    import time
    time.sleep(1.0)
    
    # Check again
    inspector = inspect(engine)
    final_tables = inspector.get_table_names()
    
    logger.info("")
    logger.info("Step 5: Verification after creation...")
    created = []
    still_missing = []
    
    for table_name in order_tables_expected:
        if table_name in final_tables:
            logger.info(f"  ✓ {table_name} now exists")
            if table_name not in existing_tables:
                created.append(table_name)
        else:
            logger.error(f"  ✗ {table_name} still missing!")
            still_missing.append(table_name)
    
    if created:
        logger.info("")
        logger.info(f"✅ Successfully created {len(created)} table(s): {', '.join(created)}")
    
    if still_missing:
        logger.error("")
        logger.error(f"❌ Failed to create {len(still_missing)} table(s): {', '.join(still_missing)}")
        logger.error("")
        logger.error("Trying individual table creation...")
        
        for table_name in still_missing:
            try:
                if table_name in Base.metadata.tables:
                    table = Base.metadata.tables[table_name]
                    logger.info(f"  Creating {table_name}...")
                    table.create(bind=engine, checkfirst=True)
                    logger.info(f"  ✓ {table_name} creation command executed")
                else:
                    logger.error(f"  ✗ {table_name} not in Base.metadata.tables!")
            except Exception as e:
                logger.error(f"  ✗ Error creating {table_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Final check
        time.sleep(1.0)
        inspector = inspect(engine)
        final_final_tables = inspector.get_table_names()
        
        logger.info("")
        logger.info("Final verification:")
        for table_name in still_missing:
            if table_name in final_final_tables:
                logger.info(f"  ✓ {table_name} now exists")
            else:
                logger.error(f"  ✗ {table_name} still missing")
    
except Exception as e:
    logger.error(f"❌ Error during table creation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("")
logger.info("="*70)
logger.info("TEST COMPLETE")
logger.info("="*70)









