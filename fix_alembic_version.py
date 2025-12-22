"""
Fix the alembic_version table to have only one row.

The overlap error is caused by having multiple rows in the alembic_version table.
This script will:
1. Show current state
2. Delete all rows
3. Insert a single row with the correct version (026)
"""
import sys
import os
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from sqlalchemy import text
from database import engine, DATABASE_URL

def fix_alembic_version():
    """Fix the alembic_version table."""
    print("="*60)
    print("Fix Alembic Version Table")
    print("="*60)
    
    with engine.connect() as connection:
        # Check current state
        print("\n1. Current state of alembic_version table:")
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        versions = [row[0] for row in result]
        
        if not versions:
            print("   Table is empty - nothing to fix")
            return
        
        print(f"   Found {len(versions)} row(s):")
        for v in versions:
            print(f"     - {v}")
        
        if len(versions) == 1:
            print("\n   ✓ Table already has only one row. No fix needed.")
            print(f"   Current version: {versions[0]}")
            return
        
        print(f"\n   ⚠️  PROBLEM: Multiple rows found! This causes the overlap error.")
        
        # The correct version should be 026 (the latest applied)
        correct_version = "026_add_member_profile_photo_url"
        
        print(f"\n2. Fixing alembic_version table...")
        print(f"   Will set version to: {correct_version}")
        
        # Delete all rows
        connection.execute(text("DELETE FROM alembic_version"))
        print("   ✓ Deleted all existing rows")
        
        # Insert the correct single row
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": correct_version}
        )
        print(f"   ✓ Inserted single row with version: {correct_version}")
        
        # Commit the transaction
        connection.commit()
        print("   ✓ Changes committed")
        
        # Verify
        print("\n3. Verifying fix...")
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        new_versions = [row[0] for row in result]
        
        if len(new_versions) == 1 and new_versions[0] == correct_version:
            print(f"   ✓ SUCCESS! Table now has one row: {new_versions[0]}")
        else:
            print(f"   ⚠️  WARNING: Unexpected state after fix: {new_versions}")
    
    print("\n" + "="*60)
    print("Fix complete! You can now run: alembic upgrade head")
    print("="*60)

if __name__ == "__main__":
    try:
        fix_alembic_version()
    except Exception as e:
        print(f"\nError during fix: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

