"""Make location tracking identifiers optional and add server-side tracking

Revision ID: 042_make_location_tracking_optional
Revises: 041_add_location_tracking_table
Create Date: 2025-01-21

Makes ga_cookie_id nullable and adds server_session_id and browser_fingerprint_hash columns.
All tracking identifiers are now optional enrichment data.
Backward compatible - existing records remain valid.
"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '042_make_location_tracking_optional'
down_revision = '041_add_location_tracking_table'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """
    Make ga_cookie_id nullable and add server_session_id and browser_fingerprint_hash columns.
    All tracking identifiers are now optional enrichment data.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Check if table exists
    if 'user_location_tracking' not in tables:
        logger.warning("user_location_tracking table does not exist, skipping migration")
        return
    
    # Check existing columns
    columns = {col['name']: col for col in inspector.get_columns('user_location_tracking')}
    
    # Make ga_cookie_id nullable (if it exists and is not nullable)
    if 'ga_cookie_id' in columns and not columns['ga_cookie_id']['nullable']:
        op.alter_column(
            'user_location_tracking',
            'ga_cookie_id',
            existing_type=sa.String(length=100),
            nullable=True,
            existing_nullable=False
        )
        logger.info("Made ga_cookie_id nullable in user_location_tracking table")
    
    # Add server_session_id column (if it doesn't exist)
    if 'server_session_id' not in columns:
        op.add_column(
            'user_location_tracking',
            sa.Column('server_session_id', sa.String(length=100), nullable=True)
        )
        # Create index for server_session_id
        op.create_index(
            'ix_user_location_tracking_server_session_id',
            'user_location_tracking',
            ['server_session_id'],
            unique=False
        )
        logger.info("Added server_session_id column to user_location_tracking table")
    
    # Add browser_fingerprint_hash column (if it doesn't exist)
    if 'browser_fingerprint_hash' not in columns:
        op.add_column(
            'user_location_tracking',
            sa.Column('browser_fingerprint_hash', sa.String(length=64), nullable=True)
        )
        # Create index for browser_fingerprint_hash
        op.create_index(
            'ix_user_location_tracking_browser_fingerprint_hash',
            'user_location_tracking',
            ['browser_fingerprint_hash'],
            unique=False
        )
        logger.info("Added browser_fingerprint_hash column to user_location_tracking table")


def downgrade() -> None:
    """
    Revert changes: make ga_cookie_id NOT NULL and remove new columns.
    WARNING: This will fail if any records have NULL ga_cookie_id.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Check if table exists
    if 'user_location_tracking' not in tables:
        logger.warning("user_location_tracking table does not exist, skipping downgrade")
        return
    
    columns = {col['name']: col for col in inspector.get_columns('user_location_tracking')}
    
    # Remove new columns if they exist
    if 'browser_fingerprint_hash' in columns:
        op.drop_index('ix_user_location_tracking_browser_fingerprint_hash', table_name='user_location_tracking')
        op.drop_column('user_location_tracking', 'browser_fingerprint_hash')
        logger.info("Dropped browser_fingerprint_hash column from user_location_tracking table")
    
    if 'server_session_id' in columns:
        op.drop_index('ix_user_location_tracking_server_session_id', table_name='user_location_tracking')
        op.drop_column('user_location_tracking', 'server_session_id')
        logger.info("Dropped server_session_id column from user_location_tracking table")
    
    # Revert ga_cookie_id to NOT NULL (will fail if NULL values exist)
    if 'ga_cookie_id' in columns and columns['ga_cookie_id']['nullable']:
        # Check if any NULL values exist
        result = connection.execute(sa.text(
            "SELECT COUNT(*) FROM user_location_tracking WHERE ga_cookie_id IS NULL"
        ))
        null_count = result.scalar()
        
        if null_count > 0:
            logger.warning(
                f"Cannot revert ga_cookie_id to NOT NULL: {null_count} records have NULL values. "
                "Please update these records before downgrading."
            )
            raise ValueError(
                f"Cannot downgrade: {null_count} records have NULL ga_cookie_id. "
                "Update or delete these records first."
            )
        
        op.alter_column(
            'user_location_tracking',
            'ga_cookie_id',
            existing_type=sa.String(length=100),
            nullable=False,
            existing_nullable=True
        )
        logger.info("Reverted ga_cookie_id to NOT NULL in user_location_tracking table")

