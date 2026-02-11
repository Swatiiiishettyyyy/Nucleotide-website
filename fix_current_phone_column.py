"""
Fix script to add current_phone and new_phone columns to account_feedback_requests table.
This script checks if the columns exist and adds them if missing.
"""
from database import engine
from sqlalchemy import text, inspect

def fix_phone_columns():
    """Add current_phone and new_phone columns to account_feedback_requests if they don't exist."""
    inspector = inspect(engine)
    
    # Check if table exists
    if "account_feedback_requests" not in inspector.get_table_names():
        print("Table 'account_feedback_requests' does not exist. Please run migrations first.")
        return False
    
    # Get existing columns
    columns = {col["name"] for col in inspector.get_columns("account_feedback_requests")}
    
    success = True
    
    # Check and add current_phone column
    if "current_phone" not in columns:
        print("Adding 'current_phone' column to 'account_feedback_requests' table...")
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE account_feedback_requests 
                    ADD COLUMN current_phone VARCHAR(50) NULL
                """))
            print("[SUCCESS] Successfully added 'current_phone' column.")
        except Exception as e:
            print(f"[ERROR] Error adding 'current_phone' column: {e}")
            success = False
    else:
        print("Column 'current_phone' already exists.")
    
    # Check and add new_phone column
    if "new_phone" not in columns:
        print("Adding 'new_phone' column to 'account_feedback_requests' table...")
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE account_feedback_requests 
                    ADD COLUMN new_phone VARCHAR(50) NULL
                """))
            print("[SUCCESS] Successfully added 'new_phone' column.")
        except Exception as e:
            print(f"[ERROR] Error adding 'new_phone' column: {e}")
            success = False
    else:
        print("Column 'new_phone' already exists.")
    
    return success

if __name__ == "__main__":
    print("=" * 60)
    print("Fixing account_feedback_requests phone columns")
    print("=" * 60)
    success = fix_phone_columns()
    if success:
        print("\n[SUCCESS] Fix completed successfully!")
    else:
        print("\n[ERROR] Fix failed. Please check the error messages above.")
    print("=" * 60)

