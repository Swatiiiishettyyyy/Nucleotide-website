"""Add user_location_tracking table

Revision ID: 041_add_location_tracking_table
Revises: 040_add_dual_token_strategy
Create Date: 2025-01-20

Adds user_location_tracking table for capturing user locations with GA Cookie integration.
Supports both authenticated and anonymous users.
GDPR compliant with 90-day data retention policy.
"""
from typing import Sequence, Union
import logging
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '041_add_location_tracking_table'
down_revision = '040_add_dual_token_strategy'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """
    Create user_location_tracking table.
    Stores location data linked to GA Cookie ID with optional user authentication.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Create user_location_tracking table if it doesn't exist
    if 'user_location_tracking' not in tables:
        op.create_table(
            'user_location_tracking',
            sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
            sa.Column('ga_cookie_id', sa.String(length=100), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('latitude', sa.Numeric(precision=10, scale=8), nullable=False),
            sa.Column('longitude', sa.Numeric(precision=11, scale=8), nullable=False),
            sa.Column('location_accuracy', sa.Integer(), nullable=True),
            sa.Column('consent_given', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('capture_method', sa.Enum('browser_geolocation', 'ip_based', name='capturemethod', create_constraint=True), nullable=False, server_default='browser_geolocation'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            
            # Foreign key to users table (ON DELETE SET NULL for GDPR compliance)
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            
            # Primary key and indexes
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for fast lookups
        op.create_index('ix_user_location_tracking_id', 'user_location_tracking', ['id'], unique=False)
        op.create_index('ix_user_location_tracking_ga_cookie_id', 'user_location_tracking', ['ga_cookie_id'], unique=False)
        op.create_index('ix_user_location_tracking_user_id', 'user_location_tracking', ['user_id'], unique=False)
        op.create_index('ix_user_location_tracking_created_at', 'user_location_tracking', ['created_at'], unique=False)
        
        logger.info("Created user_location_tracking table with indexes")
    else:
        logger.info("user_location_tracking table already exists, skipping creation")


def downgrade() -> None:
    """
    Drop user_location_tracking table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'user_location_tracking' in tables:
        # Drop indexes first
        op.drop_index('ix_user_location_tracking_created_at', table_name='user_location_tracking')
        op.drop_index('ix_user_location_tracking_user_id', table_name='user_location_tracking')
        op.drop_index('ix_user_location_tracking_ga_cookie_id', table_name='user_location_tracking')
        op.drop_index('ix_user_location_tracking_id', table_name='user_location_tracking')
        
        # Drop table
        op.drop_table('user_location_tracking')
        
        # Drop enum type if exists (MySQL doesn't use separate enum types)
        # For PostgreSQL, you might need to drop the enum type separately
        
        logger.info("Dropped user_location_tracking table")
    else:
        logger.info("user_location_tracking table does not exist, skipping drop")

