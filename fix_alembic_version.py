from database import engine
from sqlalchemy import text

# Check current version
with engine.begin() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version'))
    rows = result.fetchall()
    
    if rows:
        print(f"Found {len(rows)} row(s) in alembic_version table:")
        for row in rows:
            print(f"  - {row[0]}")
        
        # The correct version should be the full revision ID
        correct_version = "048_add_razorpay_invoice_fields_to_orders"
        
        # Check if any row matches the correct version
        current_versions = [row[0] for row in rows]
        if correct_version in current_versions and len(rows) == 1:
            print(f"\nVersion is already correct: {correct_version}")
        else:
            print(f"\nFixing alembic_version table...")
            # Delete all existing rows
            conn.execute(text("DELETE FROM alembic_version"))
            # Insert the correct single row
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": correct_version})
            print(f"Updated to correct version: {correct_version}")
    else:
        print("No version found in alembic_version table")
        # Insert the correct version
        correct_version = "048_add_razorpay_invoice_fields_to_orders"
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": correct_version})
        print(f"Inserted correct version: {correct_version}")
