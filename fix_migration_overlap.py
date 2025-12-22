"""
Fix Alembic migration overlap issue between revisions 025 and 026.

The error "Requested revision 026_add_member_profile_photo_url overlaps with 
other requested revisions 025_rename_metadata_to_transfer_metadata" occurs 
when Alembic detects a conflict in the migration chain.

This script fixes the issue by:
1. Creating a merge migration to resolve the overlap
2. Updating revision 027 to depend on the merge migration

Run: python fix_migration_overlap.py
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    # Use absolute path for venv python
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if cmd.startswith(".\\venv\\"):
        # Convert relative path to absolute
        venv_python = os.path.join(script_dir, "venv", "Scripts", "python.exe")
        if os.path.exists(venv_python):
            cmd = cmd.replace(".\\venv\\Scripts\\python.exe", venv_python)
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        # Only show stderr if it's not just INFO messages
        if "INFO" not in result.stderr or "ERROR" in result.stderr:
            print("STDERR:", result.stderr)
    
    return result.returncode == 0, result.stdout, result.stderr

def main():
    """Main function to fix the migration overlap."""
    print("="*60)
    print("Alembic Migration Overlap Fix Script")
    print("="*60)
    
    # Get the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Step 1: Check current state
    print("\n1. Checking current migration state...")
    success, output, error = run_command(
        ".\venv\Scripts\python.exe -m alembic current",
        "Check current database revision"
    )
    
    # Step 2: Create merge migration
    # Even though 026 depends on 025 (linear chain), creating a merge migration
    # will help Alembic resolve the overlap error by explicitly merging the branches
    print("\n2. Creating merge migration to resolve overlap...")
    merge_revision_id = "028_merge_025_026"
    merge_file_path = script_dir / "alembic" / "versions" / f"{merge_revision_id}.py"
    
    if merge_file_path.exists():
        print(f"[WARNING] Merge migration already exists: {merge_file_path}")
        print("   Skipping creation. Delete it first if you want to recreate.")
    else:
        # Create the merge migration file
        merge_migration_content = '''"""Merge revisions 025 and 026

Revision ID: 028_merge_025_026
Revises: ('025_rename_metadata_to_transfer_metadata', '026_add_member_profile_photo_url')
Create Date: 2025-01-20

This merge migration resolves the overlap between revisions 025 and 026.
Even though 026 depends on 025 in the file structure, this merge ensures 
Alembic recognizes the proper chain and resolves the overlap error.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "028_merge_025_026"
down_revision = ("025_rename_metadata_to_transfer_metadata", "026_add_member_profile_photo_url")
branch_labels = None
depends_on = None


def upgrade():
    """
    Merge migration - no changes needed as both migrations are already applied.
    This migration exists only to merge the revision branches and resolve the overlap.
    """
    pass


def downgrade():
    """
    Merge migration - no changes needed.
    """
    pass
'''
        
        print(f"Creating merge migration file: {merge_file_path}")
        try:
            with open(merge_file_path, 'w', encoding='utf-8') as f:
                f.write(merge_migration_content)
            print(f"[OK] Merge migration created successfully!")
        except Exception as e:
            print(f"[ERROR] Error creating merge migration: {e}")
            return
    
    # Step 3: Update 027 to depend on the merge migration
    print("\n3. Updating revision 027 to depend on merge migration...")
    migration_027_path = script_dir / "alembic" / "versions" / "027_update_payment_status_enums.py"
    
    if not migration_027_path.exists():
        print(f"[ERROR] Migration file 027 not found at {migration_027_path}")
        return
    
    with open(migration_027_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update down_revision from 026 to 028
    old_down_revision = 'down_revision = "026_add_member_profile_photo_url"'
    new_down_revision = 'down_revision = "028_merge_025_026"'
    
    if old_down_revision in content:
        content = content.replace(old_down_revision, new_down_revision)
        # Also update the docstring
        if 'Revises: 026_add_member_profile_photo_url' in content:
            content = content.replace(
                'Revises: 026_add_member_profile_photo_url',
                'Revises: 028_merge_025_026'
            )
        with open(migration_027_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Updated revision 027 to depend on merge migration 028")
    elif 'down_revision = "028_merge_025_026"' in content:
        print(f"[OK] Revision 027 already depends on merge migration 028")
    else:
        print(f"[WARNING] Could not find expected down_revision in 027.")
        print(f"  Current down_revision line:")
        for line in content.split('\n'):
            if 'down_revision' in line:
                print(f"    {line.strip()}")
        print(f"\n  Please manually update to:")
        print(f"    down_revision = \"028_merge_025_026\"")
    
    # Step 4: Verify the fix
    print("\n4. Verifying migration chain...")
    success, output, error = run_command(
        ".\venv\Scripts\python.exe -m alembic heads",
        "Verify migration heads after fix"
    )
    
    if success and "027_update_payment_status_enums" in output:
        print("[OK] Migration chain verified successfully!")
    else:
        print("[WARNING] Migration chain verification had issues. Check output above.")
    
    print("\n" + "="*60)
    print("Fix script completed!")
    print("="*60)
    print("\nNext steps:")
    print("1. Review the merge migration file: alembic/versions/028_merge_025_026.py")
    print("2. Run the migration:")
    print("   .\\venv\\Scripts\\python.exe -m alembic upgrade head")
    print("   OR")
    print("   .\\venv\\Scripts\\python.exe -m alembic upgrade 027_update_payment_status_enums")
    print("3. The overlap error should now be resolved")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
