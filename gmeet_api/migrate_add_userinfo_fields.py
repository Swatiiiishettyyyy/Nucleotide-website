"""
Migration script to add new userinfo fields to counsellor_gmeet_list table.

Run this script if the table already exists and you need to add the new columns:
- given_name
- family_name
- email_verified
- locale

Usage:
    python -m gmeet_api.migrate_add_userinfo_fields
    OR
    cd Nucleotide-website_v11 && python -m gmeet_api.migrate_add_userinfo_fields
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


def migrate_add_userinfo_fields():
    """Add new columns to counsellor_gmeet_list table if they don't exist."""
    try:
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = 'counsellor_gmeet_list'
            """))
            
            table_exists = result.fetchone()[0] > 0
            
            if not table_exists:
                logger.warning("Table 'counsellor_gmeet_list' does not exist. Run create_tables.py first.")
                return
            
            # Add columns if they don't exist
            columns_to_add = [
                ("given_name", "VARCHAR(255) NULL"),
                ("family_name", "VARCHAR(255) NULL"),
                ("email_verified", "BOOLEAN NULL"),
                ("locale", "VARCHAR(10) NULL")
            ]
            
            for column_name, column_def in columns_to_add:
                try:
                    # Check if column exists
                    result = conn.execute(text(f"""
                        SELECT COUNT(*) as count
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                        AND table_name = 'counsellor_gmeet_list'
                        AND column_name = '{column_name}'
                    """))
                    
                    column_exists = result.fetchone()[0] > 0
                    
                    if not column_exists:
                        logger.info(f"Adding column: {column_name}")
                        conn.execute(text(f"""
                            ALTER TABLE counsellor_gmeet_list
                            ADD COLUMN {column_name} {column_def}
                        """))
                        conn.commit()
                        logger.info(f"✅ Added column: {column_name}")
                    else:
                        logger.info(f"Column {column_name} already exists, skipping")
                        
                except Exception as e:
                    logger.error(f"Error adding column {column_name}: {e}")
                    conn.rollback()
                    raise
            
            logger.info("✅ Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate_add_userinfo_fields()

