"""fix_phone_change_audit_logs_request_id

Revision ID: 7b9cfffc6882
Revises: e644dba652bf
Create Date: 2025-12-26 18:40:00.000000

Tags: phone_change, fix
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect


# revision identifiers, used by Alembic.
revision: str = '7b9cfffc6882'
down_revision: Union[str, None] = 'e644dba652bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add request_id column to phone_change_audit_logs if it doesn't exist
    This fixes the case where the table was created before the migration ran
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if table exists
    if 'phone_change_audit_logs' not in inspector.get_table_names():
        return  # Table doesn't exist, skip
    
    # Check if request_id column exists
    columns = [col['name'] for col in inspector.get_columns('phone_change_audit_logs')]
    
    if 'request_id' not in columns:
        # Add request_id column
        if dialect_name == 'mysql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN request_id INTEGER NULL,
                ADD INDEX ix_phone_change_audit_logs_request_id (request_id),
                ADD CONSTRAINT fk_phone_change_audit_logs_request_id
                    FOREIGN KEY (request_id) REFERENCES phone_change_requests(id) ON DELETE SET NULL
            """))
        elif dialect_name == 'postgresql':
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN request_id INTEGER,
                ADD CONSTRAINT fk_phone_change_audit_logs_request_id
                    FOREIGN KEY (request_id) REFERENCES phone_change_requests(id) ON DELETE SET NULL
            """))
            # Create index separately for PostgreSQL
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_request_id 
                ON phone_change_audit_logs(request_id)
            """))
        else:
            # SQLite
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                ADD COLUMN request_id INTEGER
            """))
            # SQLite doesn't support adding foreign keys after table creation easily
            # Index creation
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_phone_change_audit_logs_request_id 
                ON phone_change_audit_logs(request_id)
            """))


def downgrade() -> None:
    """
    Remove request_id column from phone_change_audit_logs
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if table exists
    if 'phone_change_audit_logs' not in inspector.get_table_names():
        return
    
    # Check if request_id column exists
    columns = [col['name'] for col in inspector.get_columns('phone_change_audit_logs')]
    
    if 'request_id' in columns:
        if dialect_name == 'mysql':
            # Drop foreign key constraint first
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                DROP FOREIGN KEY fk_phone_change_audit_logs_request_id
            """))
            # Drop index (check if exists first for MySQL)
            try:
                connection.execute(text("""
                    DROP INDEX ix_phone_change_audit_logs_request_id 
                    ON phone_change_audit_logs
                """))
            except Exception:
                pass  # Index doesn't exist, ignore
            # Drop column
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                DROP COLUMN request_id
            """))
        elif dialect_name == 'postgresql':
            # Drop foreign key constraint
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                DROP CONSTRAINT IF EXISTS fk_phone_change_audit_logs_request_id
            """))
            # Drop index
            connection.execute(text("""
                DROP INDEX IF EXISTS ix_phone_change_audit_logs_request_id
            """))
            # Drop column
            connection.execute(text("""
                ALTER TABLE phone_change_audit_logs
                DROP COLUMN request_id
            """))
        else:
            # SQLite - doesn't support dropping columns easily
            # This would require recreating the table
            pass
