"""Add tracking_records table

Revision ID: 045_add_tracking_records_table
Revises: 044_add_newsletter_subscriptions_table
Create Date: 2026-01-13

Adds tracking_records table for location and analytics tracking with consent management.
Supports both authenticated and anonymous users.
All fields default to NULL except consent flags (default FALSE) and timestamps (auto-generated).
"""
from typing import Sequence, Union
import logging
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, postgresql

# revision identifiers, used by Alembic.
revision = '045_add_tracking_records_table'
down_revision = '044_add_newsletter_subscriptions_table'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """
    Create tracking_records table.
    Stores location and analytics data with consent-based conditional storage.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Create tracking_records table if it doesn't exist
    if 'tracking_records' not in tables:
        # Check if we're using PostgreSQL (for UUID support)
        is_postgres = connection.dialect.name == 'postgresql'
        
        if is_postgres:
            # PostgreSQL: Use native UUID type
            record_id_column = sa.Column(
                'record_id',
                postgresql.UUID(as_uuid=False),
                primary_key=True,
                server_default=sa.text('gen_random_uuid()')
            )
        else:
            # Other databases: Use String for UUID
            record_id_column = sa.Column(
                'record_id',
                sa.String(36),
                primary_key=True
            )
        
        op.create_table(
            'tracking_records',
            record_id_column,
            
            # User Identity (NULL for anonymous)
            sa.Column('user_id', sa.String(length=255), nullable=True),
            sa.Column('ga_client_id', sa.String(length=255), nullable=True),
            sa.Column('session_id', sa.String(length=255), nullable=True),
            
            # Consent Flags (DEFAULT FALSE)
            sa.Column('ga_consent', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('location_consent', sa.Boolean(), nullable=False, server_default='0'),
            
            # Location Data (NULL by default)
            sa.Column('latitude', sa.Numeric(precision=10, scale=8), nullable=True),
            sa.Column('longitude', sa.Numeric(precision=11, scale=8), nullable=True),
            sa.Column('accuracy', sa.Float(), nullable=True),
            
            # Page Context (NULL by default)
            sa.Column('page_url', sa.String(length=500), nullable=True),
            sa.Column('referrer', sa.String(length=500), nullable=True),
            
            # Device Information (NULL by default)
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('device_type', sa.String(length=50), nullable=True),
            sa.Column('browser', sa.String(length=100), nullable=True),
            sa.Column('operating_system', sa.String(length=100), nullable=True),
            sa.Column('language', sa.String(length=20), nullable=True),
            sa.Column('timezone', sa.String(length=100), nullable=True),
            
            # Network Information
            sa.Column('ip_address', sa.String(length=45), nullable=True),  # Supports both IPv4 and IPv6
            
            # Metadata
            sa.Column('record_type', sa.String(length=50), nullable=True),  # 'consent_update', 'location_update', 'page_view'
            
            # Timestamps (ALWAYS populated)
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('consent_updated_at', sa.DateTime(timezone=True), nullable=True),
            
            # Primary key
            sa.PrimaryKeyConstraint('record_id')
        )
        
        # Create indexes for performance
        op.create_index('idx_user_id', 'tracking_records', ['user_id'], unique=False)
        op.create_index('idx_ga_client_id', 'tracking_records', ['ga_client_id'], unique=False)
        op.create_index('idx_session_id', 'tracking_records', ['session_id'], unique=False)
        op.create_index('idx_created_at', 'tracking_records', ['created_at'], unique=False)
        op.create_index('idx_consent_flags', 'tracking_records', ['ga_consent', 'location_consent'], unique=False)
        
        logger.info("Created tracking_records table with indexes")
    else:
        logger.info("tracking_records table already exists, skipping creation")


def downgrade() -> None:
    """
    Drop tracking_records table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'tracking_records' in tables:
        # Drop indexes first
        op.drop_index('idx_consent_flags', table_name='tracking_records')
        op.drop_index('idx_created_at', table_name='tracking_records')
        op.drop_index('idx_session_id', table_name='tracking_records')
        op.drop_index('idx_ga_client_id', table_name='tracking_records')
        op.drop_index('idx_user_id', table_name='tracking_records')
        
        # Drop table
        op.drop_table('tracking_records')
        logger.info("Dropped tracking_records table")
    else:
        logger.info("tracking_records table does not exist, skipping drop")


