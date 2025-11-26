"""Add missing columns to device_sessions table

Revision ID: 007_device_sessions
Revises: 006_audit_identifiers
Create Date: 2024-01-07 00:00:00.000000

Tags: sessions, device, authentication
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '007_device_sessions'
down_revision: Union[str, None] = '006_audit_identifiers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add missing columns to device_sessions table:
    - session_token (with unique index)
    - browser_info
    - last_active
    - event_on_logout
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    if 'device_sessions' not in inspector.get_table_names():
        return
    
    device_session_columns = {col['name'] for col in inspector.get_columns('device_sessions')}
    
    # Add session_token column
    if 'session_token' not in device_session_columns:
        # Check if there are existing records
        result = connection.execute(sa.text("SELECT COUNT(*) as cnt FROM device_sessions"))
        row = result.fetchone()
        has_existing_records = row[0] > 0 if row else False
        
        if has_existing_records:
            # Add as nullable first
            op.add_column('device_sessions', sa.Column('session_token', sa.String(length=255), nullable=True))
            
            # Copy from session_key if it exists
            if 'session_key' in device_session_columns:
                connection.execute(sa.text("""
                    UPDATE device_sessions 
                    SET session_token = session_key 
                    WHERE session_token IS NULL AND session_key IS NOT NULL
                """))
            
            # Generate tokens for remaining NULL values
            if dialect_name == 'mysql':
                connection.execute(sa.text("""
                    UPDATE device_sessions 
                    SET session_token = CONCAT('temp_', id, '_', UNIX_TIMESTAMP())
                    WHERE session_token IS NULL
                """))
            else:
                connection.execute(sa.text("""
                    UPDATE device_sessions 
                    SET session_token = 'temp_' || id || '_' || CAST(strftime('%s', 'now') AS TEXT)
                    WHERE session_token IS NULL
                """))
            
            # Make it NOT NULL
            op.alter_column('device_sessions', 'session_token', nullable=False)
        else:
            # No existing records, add as NOT NULL directly
            op.add_column('device_sessions', sa.Column('session_token', sa.String(length=255), nullable=False))
        
        # Create unique index
        op.create_index('ix_device_sessions_session_token', 'device_sessions', ['session_token'], unique=True)
    
    # Add browser_info column
    if 'browser_info' not in device_session_columns:
        op.add_column('device_sessions', sa.Column('browser_info', sa.Text(), nullable=True))
    
    # Add last_active column
    if 'last_active' not in device_session_columns:
        result = connection.execute(sa.text("SELECT COUNT(*) as cnt FROM device_sessions"))
        row = result.fetchone()
        has_existing_records = row[0] > 0 if row else False
        
        if dialect_name == 'mysql':
            if has_existing_records:
                op.add_column('device_sessions', sa.Column('last_active', sa.DateTime(timezone=True), nullable=True))
                connection.execute(sa.text("""
                    UPDATE device_sessions 
                    SET last_active = COALESCE(created_at, NOW()) 
                    WHERE last_active IS NULL
                """))
                op.alter_column('device_sessions', 'last_active', 
                              type_=sa.DateTime(timezone=True),
                              nullable=False,
                              server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
            else:
                op.add_column('device_sessions', sa.Column('last_active', 
                              sa.DateTime(timezone=True), 
                              nullable=False,
                              server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')))
        else:
            if has_existing_records:
                op.add_column('device_sessions', sa.Column('last_active', sa.DateTime(timezone=True), nullable=True))
                connection.execute(sa.text("""
                    UPDATE device_sessions 
                    SET last_active = COALESCE(created_at, CURRENT_TIMESTAMP) 
                    WHERE last_active IS NULL
                """))
                op.alter_column('device_sessions', 'last_active', nullable=False)
            else:
                op.add_column('device_sessions', sa.Column('last_active', 
                              sa.DateTime(timezone=True), 
                              nullable=False,
                              server_default=sa.text('CURRENT_TIMESTAMP')))
        
        op.create_index('ix_device_sessions_last_active', 'device_sessions', ['last_active'], unique=False)
    
    # Add event_on_logout column
    if 'event_on_logout' not in device_session_columns:
        if dialect_name == 'mysql':
            op.add_column('device_sessions', sa.Column('event_on_logout', sa.DateTime(timezone=True), nullable=True))
        else:
            op.add_column('device_sessions', sa.Column('event_on_logout', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove device session columns"""
    op.drop_index('ix_device_sessions_last_active', table_name='device_sessions')
    op.drop_index('ix_device_sessions_session_token', table_name='device_sessions')
    op.drop_column('device_sessions', 'event_on_logout')
    op.drop_column('device_sessions', 'last_active')
    op.drop_column('device_sessions', 'browser_info')
    op.drop_column('device_sessions', 'session_token')

