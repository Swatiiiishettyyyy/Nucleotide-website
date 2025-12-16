"""
Script to verify if consent_products table exists and check its data.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from database import engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from Consent_module.Consent_model import ConsentProduct

def verify_consent_products():
    """Verify if consent_products table exists and check its contents."""
    print("=" * 60)
    print("Verifying consent_products table...")
    print("=" * 60)
    
    try:
        # Check if table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'consent_products' in tables:
            print("✓ consent_products table EXISTS")
            print()
            
            # Get table columns
            columns = inspector.get_columns('consent_products')
            print(f"Table Structure ({len(columns)} columns):")
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")
            print()
            
            # Check data
            db = Session(engine)
            try:
                products = db.query(ConsentProduct).all()
                print(f"✓ Found {len(products)} consent products:")
                print()
                
                if products:
                    for product in products:
                        print(f"  ID: {product.id:2d} | Name: {product.name}")
                    print()
                    print(f"Total: {len(products)} products")
                else:
                    print("  ⚠ Warning: Table exists but is EMPTY")
                    print("  Run migration to seed data: alembic upgrade head")
                
            except Exception as e:
                print(f"✗ Error querying data: {str(e)}")
            finally:
                db.close()
                
        else:
            print("✗ consent_products table DOES NOT EXIST")
            print()
            print("Available tables:")
            for table in sorted(tables):
                print(f"  - {table}")
            print()
            print("To create the table, run:")
            print("  alembic upgrade head")
            
    except Exception as e:
        print(f"✗ Error checking database: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)

if __name__ == "__main__":
    verify_consent_products()


