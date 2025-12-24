"""
Fix Alembic version from 33 to 34.

This script will:
1. Check the current database revision
2. If it's 33, upgrade it to 34 (the latest)
"""
import sys
import os
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from sqlalchemy import text
from database import engine, DATABASE_URL
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

def fix_alembic_to_34():
    """Fix Alembic version from 33 to 34."""
    print("="*60)
    print("Fix Alembic Version: 33 -> 34")
    print("="*60)
    
    # Create Alembic configuration
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    
    # Check current version
    print("\n1. Checking current database revision...")
    try:
        with engine.connect() as connection:
            # First check if there are multiple rows (which causes the error)
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]
            
            if not versions:
                print("   ⚠️  No revision found in database. Run initial migration first.")
                return
            
            print(f"   Found {len(versions)} row(s) in alembic_version table:")
            for v in versions:
                print(f"     - {v}")
            
            # If multiple rows, clean them up first
            if len(versions) > 1:
                print("\n   WARNING: Multiple rows found! Cleaning up...")
                # Delete all rows
                connection.execute(text("DELETE FROM alembic_version"))
                # Insert single row with revision 33 (assuming that's the actual current state)
                # We'll upgrade to 34 in the next step
                connection.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                    {"version": "033_remove_member_transfer_system"}
                )
                connection.commit()
                print("   SUCCESS: Cleaned up multiple rows, set to revision 33")
            
            # Now check the current revision properly
            context = MigrationContext.configure(connection)
            try:
                current_rev = context.get_current_revision()
            except Exception:
                # If still having issues, get from table directly
                result = connection.execute(text("SELECT version_num FROM alembic_version"))
                versions = [row[0] for row in result]
                current_rev = versions[0] if versions else None
            
            if current_rev is None:
                print("   WARNING: No revision found in database. Run initial migration first.")
                return
            
            print(f"   Current revision: {current_rev}")
            
            if current_rev == "034_add_placed_by_member_id":
                print("   SUCCESS: Database is already at revision 34. No fix needed.")
                return
            
            if current_rev != "033_remove_member_transfer_system":
                print(f"   WARNING: Current revision is {current_rev}, expected 33.")
                print("   Will attempt to upgrade to head anyway...")
            else:
                print("   SUCCESS: Found revision 33 as expected.")
            
    except Exception as e:
        print(f"   Error checking current revision: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check what the head revision is
    print("\n2. Checking latest available revision...")
    try:
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        print(f"   Latest available revision: {head_rev}")
        
        if head_rev != "034_add_placed_by_member_id":
            print(f"   WARNING: Head revision is {head_rev}, not 34!")
    except Exception as e:
        print(f"   Error checking head revision: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Upgrade to head
    print("\n3. Upgrading database to revision 34 (head)...")
    try:
        command.upgrade(alembic_cfg, "head")
        print("   SUCCESS: Upgrade command completed")
    except Exception as e:
        print(f"   Error during upgrade: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Verify the new version
    print("\n4. Verifying new revision...")
    try:
        with engine.connect() as connection:
            # Check table directly to avoid multiple heads error
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]
            
            if len(versions) > 1:
                print(f"   WARNING: Still found {len(versions)} rows. Cleaning up again...")
                # Keep only the latest one (34)
                connection.execute(text("DELETE FROM alembic_version"))
                connection.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                    {"version": "034_add_placed_by_member_id"}
                )
                connection.commit()
                print("   SUCCESS: Cleaned up, set to revision 34")
                versions = ["034_add_placed_by_member_id"]
            
            if len(versions) == 1:
                new_rev = versions[0]
                if new_rev == "034_add_placed_by_member_id" or new_rev.startswith("034"):
                    print(f"   SUCCESS! Database is now at revision 34: {new_rev}")
                else:
                    print(f"   WARNING: Database revision is {new_rev}, expected 34")
            else:
                print(f"   ERROR: Unexpected state - found {len(versions)} rows")
    except Exception as e:
        print(f"   Error verifying revision: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("Fix complete!")
    print("="*60)

if __name__ == "__main__":
    try:
        fix_alembic_to_34()
    except Exception as e:
        print(f"\nError during fix: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

