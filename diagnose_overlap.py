"""
Diagnose why Alembic is reporting an overlap error between 025 and 026.

The overlap error typically occurs when:
1. The database's alembic_version table has inconsistent state
2. There are multiple heads in the migration tree
3. A previous merge migration left the database in an inconsistent state
"""
import sys
import os
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from database import engine, DATABASE_URL

def diagnose_overlap():
    """Diagnose the overlap issue."""
    print("="*60)
    print("Alembic Overlap Diagnosis")
    print("="*60)
    
    # Setup Alembic
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    script = ScriptDirectory.from_config(alembic_cfg)
    
    # Get current database revision
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        
        # Check what's in the alembic_version table FIRST
        print(f"\n1. Checking alembic_version table...")
        try:
            from sqlalchemy import text
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]
            print(f"   Versions in alembic_version table: {versions}")
            
            if len(versions) > 1:
                print("   ⚠️  ⚠️  ⚠️  CRITICAL: Multiple versions found!")
                print("   This is the root cause of the overlap error!")
                print("   The alembic_version table should only have ONE row.")
                print(f"   Found {len(versions)} rows: {versions}")
            elif len(versions) == 1:
                print(f"   ✓ Single version found: {versions[0]}")
            else:
                print("   ⚠️  No versions found (empty table)")
        except Exception as e:
            print(f"   Error querying alembic_version: {e}")
        
        # Try to get current revision (may fail if multiple heads)
        print(f"\n2. Current Database Revision:")
        try:
            current_rev = context.get_current_revision()
            print(f"   Current revision: {current_rev}")
        except Exception as e:
                print(f"   ERROR: Cannot get single current revision: {e}")
            try:
                current_heads = context.get_current_heads()
                print(f"   Multiple heads detected: {current_heads}")
                print("   ⚠️  This confirms the overlap issue!")
            except Exception as e2:
                print(f"   Error getting heads: {e2}")
            current_rev = None
    
    # Check migration heads
    heads = script.get_revisions("head")
    print(f"\n3. Migration Heads: {[str(h.revision) for h in heads]}")
    
    if len(heads) > 1:
        print("   ⚠️  WARNING: Multiple heads detected! This indicates branching.")
    
    # Check the path from current to head
    print(f"\n4. Checking path from {current_rev} to head...")
    try:
        if current_rev:
            current_revision = script.get_revision(current_rev)
            head_revision = script.get_revision("head")
            
            # Get the upgrade path
            upgrade_path = list(script.walk_revisions(
                upper=head_revision.revision,
                lower=current_revision.revision
            ))
            
            print(f"   Upgrade path: {' → '.join([str(r.revision) for r in upgrade_path])}")
            
            # Check for 025 and 026 in the path
            path_revisions = [str(r.revision) for r in upgrade_path]
            if "025_rename_metadata_to_transfer_metadata" in path_revisions and \
               "026_add_member_profile_photo_url" in path_revisions:
                print("   ✓ Both 025 and 026 are in the upgrade path (expected)")
            else:
                print("   ⚠️  Issue: 025 or 026 missing from upgrade path")
        else:
            print("   No current revision - database might be empty")
    except Exception as e:
        print(f"   Error checking path: {e}")
        import traceback
        traceback.print_exc()
    
    # Check if 025 and 026 have correct dependencies
    print(f"\n5. Checking migration dependencies...")
    rev_025 = script.get_revision("025_rename_metadata_to_transfer_metadata")
    rev_026 = script.get_revision("026_add_member_profile_photo_url")
    
    print(f"   025 parent: {rev_025.down_revision}")
    print(f"   026 parent: {rev_026.down_revision}")
    
    if rev_026.down_revision == "025_rename_metadata_to_transfer_metadata":
        print("   ✓ 026 correctly depends on 025")
    else:
        print("   ⚠️  WARNING: 026 does not depend on 025!")
    
    # Check for any branches
    print(f"\n6. Checking for branches...")
    all_revisions = list(script.walk_revisions())
    branches = {}
    for rev in all_revisions:
        if rev.down_revision:
            if isinstance(rev.down_revision, tuple):
                print(f"   ⚠️  Found merge migration: {rev.revision} merges {rev.down_revision}")
                branches[rev.revision] = rev.down_revision
    
    if branches:
        print(f"   ⚠️  WARNING: Found {len(branches)} merge migration(s)!")
        for merge_rev, parents in branches.items():
            print(f"      {merge_rev} merges: {parents}")
    else:
        print("   ✓ No merge migrations found (linear chain)")
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
    
    print("\nMost likely causes of the overlap error:")
    print("1. The alembic_version table has multiple rows or incorrect data")
    print("2. A previous merge migration (028) was deleted but left the database in an inconsistent state")
    print("3. The database thinks it's at a different revision than what the files indicate")
    print("\nSolution:")
    print("If the database has incorrect version data, you may need to:")
    print("  - Check the alembic_version table: SELECT * FROM alembic_version;")
    print("  - If multiple rows exist, delete the incorrect ones")
    print("  - If the version is wrong, update it: UPDATE alembic_version SET version_num='026_add_member_profile_photo_url';")

if __name__ == "__main__":
    try:
        diagnose_overlap()
    except Exception as e:
        print(f"\nError during diagnosis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

