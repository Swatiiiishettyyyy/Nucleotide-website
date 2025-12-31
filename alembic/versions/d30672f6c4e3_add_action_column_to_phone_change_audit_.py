"""add_action_column_to_phone_change_audit_logs

Revision ID: d30672f6c4e3
Revises: 7b9cfffc6882
Create Date: 2025-12-26 18:56:00.000000

Tags: phone_change, fix
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'd30672f6c4e3'
down_revision: Union[str, None] = '7b9cfffc6882'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add action, status, details, timestamp, success, error_message columns to phone_change_audit_logs if missing
    This fixes the case where the table was created before the migration ran
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if table exists
    if 'phone_change_audit_logs' not in inspector.get_table_names():
        return  # Table doesn't exist, skip
    
    # Get existing columns
    columns = {col['name']: col for col in inspector.get_columns('phone_change_audit_logs')}
    
    # Add action column if missing
    if 'action' not in columns:
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN action VARCHAR(100) NOT NULL DEFAULT 'unknown'
            """))
            # Remove default after adding
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                MODIFY COLUMN action VARCHAR(100) NOT NULL
            """))
            # Add index separately
            connection.execute(text("""
                CREATE INDEX ix_phone_change_audit_logs_action 
                ON phone_change_audit_logs(action)
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN action VARCHAR(100) NOT NULL DEFAULT 'unknown'
            """))
            # Remove default after adding
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ALTER COLUMN action DROP DEFAULT
            """))
            # Create index
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_action 
                ON phone_change_audit_logs(action)
            """))
        else:
            # SQLite
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN action VARCHAR(100) NOT NULL DEFAULT 'unknown'
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_action 
                ON phone_change_audit_logs(action)
            """))
    
    # Add status column if missing
    if 'status' not in columns:
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'unknown'
            """))
            # Remove default
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                MODIFY COLUMN status VARCHAR(50) NOT NULL
            """))
            # Add index separately
            connection.execute(text("""
                CREATE INDEX ix_phone_change_audit_logs_status 
                ON phone_change_audit_logs(status)
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'unknown'
            """))
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ALTER COLUMN status DROP DEFAULT
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_status 
                ON phone_change_audit_logs(status)
            """))
        else:
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'unknown'
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_status 
                ON phone_change_audit_logs(status)
            """))
    
    # Add details column if missing (JSON type)
    if 'details' not in columns:
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN details JSON NULL
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN details JSONB NULL
            """))
        else:
            # SQLite - use TEXT for JSON
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN details TEXT NULL
            """))
    
    # Add timestamp column if missing
    if 'timestamp' not in columns:
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN timestamp DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                ADD INDEX ix_phone_change_audit_logs_timestamp (timestamp)
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_timestamp 
                ON phone_change_audit_logs(timestamp)
            """))
        else:
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_timestamp 
                ON phone_change_audit_logs(timestamp)
            """))
    
    # Add success column if missing
    if 'success' not in columns:
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN success INTEGER NOT NULL DEFAULT 1
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN success INTEGER NOT NULL DEFAULT 1
            """))
        else:
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN success INTEGER NOT NULL DEFAULT 1
            """))
    
    # Add error_message column if missing
    if 'error_message' not in columns:
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN error_message TEXT NULL
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN error_message TEXT NULL
            """))
        else:
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN error_message TEXT NULL
            """))


def downgrade() -> None:
    """
    Remove added columns (if needed for rollback)
    Note: This is destructive and will lose data
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if table exists
    if 'phone_change_audit_logs' not in inspector.get_table_names():
        return
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('phone_change_audit_logs')]
    
    # Drop columns if they exist (in reverse order to avoid dependency issues)
    if 'error_message' in columns:
        connection.execute(text("""
            ALTER TABLE phone_change_audit_logs
            DROP COLUMN error_message
        """))
    
    if 'success' in columns:
        connection.execute(text("""
            ALTER TABLE phone_change_audit_logs
            DROP COLUMN success
        """))
    
    if 'timestamp' in columns:
        # Drop index first
        try:
            connection.execute(text("""
                DROP INDEX ix_phone_change_audit_logs_timestamp ON phone_change_audit_logs
            """))
        except Exception:
            pass
        connection.execute(text("""
            ALTER TABLE phone_change_audit_logs
            DROP COLUMN timestamp
        """))
    
    if 'details' in columns:
        connection.execute(text("""
            ALTER TABLE phone_change_audit_logs
            DROP COLUMN details
        """))
    
    if 'status' in columns:
        # Drop index first
        try:
            connection.execute(text("""
                DROP INDEX ix_phone_change_audit_logs_status ON phone_change_audit_logs
            """))
        except Exception:
            pass
        connection.execute(text("""
            ALTER TABLE phone_change_audit_logs
            DROP COLUMN status
        """))
    
    if 'action' in columns:
        # Drop index first
        try:
            connection.execute(text("""
                DROP INDEX ix_phone_change_audit_logs_action ON phone_change_audit_logs
            """))
        except Exception:
            pass
        connection.execute(text("""
            ALTER TABLE phone_change_audit_logs
            DROP COLUMN action
        """))
