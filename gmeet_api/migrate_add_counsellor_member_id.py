"""
Migration script to add counsellor_member_id column to counsellor_gmeet_bookings table.

Run this script if the table already exists and you need to add the new column.

Usage:
    python -m gmeet_api.migrate_add_counsellor_member_id
    OR
    cd Nucleotide-website_v11 && python -m gmeet_api.migrate_add_counsellor_member_id
"""
import sys
from pathlib import Path
import logging
from sqlalchemy import text

# Add parent directory to path to import shared database
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_add_counsellor_member_id():
    """Add counsellor_member_id column to counsellor_gmeet_bookings table if it doesn't exist."""
    try:
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = 'counsellor_gmeet_bookings'
            """))
            
            table_exists = result.fetchone()[0] > 0
            
            if not table_exists:
                logger.warning("Table 'counsellor_gmeet_bookings' does not exist. Run create_tables.py first.")
                return
            
            # Check if column exists
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                AND table_name = 'counsellor_gmeet_bookings'
                AND column_name = 'counsellor_member_id'
            """))
            
            column_exists = result.fetchone()[0] > 0
            
            if column_exists:
                logger.info("Column 'counsellor_member_id' already exists, skipping migration")
                return
            
            # Add column
            logger.info("Adding column: counsellor_member_id")
            conn.execute(text("""
                ALTER TABLE counsellor_gmeet_bookings
                ADD COLUMN counsellor_member_id VARCHAR(255) NOT NULL DEFAULT '' AFTER counsellor_id
            """))
            
            # Add index
            logger.info("Adding index on counsellor_member_id")
            conn.execute(text("""
                CREATE INDEX ix_counsellor_gmeet_bookings_counsellor_member_id 
                ON counsellor_gmeet_bookings(counsellor_member_id)
            """))
            
            conn.commit()
            logger.info("✅ Migration completed successfully!")
            logger.info("Note: Existing rows have empty string as default. Update them with actual values if needed.")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate_add_counsellor_member_id()

