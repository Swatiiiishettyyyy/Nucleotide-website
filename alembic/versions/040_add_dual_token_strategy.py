"""Add dual-token strategy (refresh_tokens table and device_sessions modification)

Revision ID: 040_add_dual_token_strategy
Revises: 039_update_otp_verified_to_auto_consent
Create Date: 2025-01-20

Adds refresh_tokens table for dual-token strategy with token family tracking.
Modifies device_sessions table to add refresh_token_family_id column.
"""
from typing import Sequence, Union
import logging
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '040_add_dual_token_strategy'
down_revision = '039_update_otp_verified_to_auto_consent'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """
    Add refresh_tokens table and refresh_token_family_id column to device_sessions.
    Implements dual-token strategy with token rotation and reuse detection.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Create refresh_tokens table if it doesn't exist
    if 'refresh_tokens' not in tables:
        op.create_table(
            'refresh_tokens',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('token_family_id', sa.String(length=36), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['session_id'], ['device_sessions.id'], ondelete='CASCADE')
        )
        
        # Create indexes
        op.create_index(op.f('ix_refresh_tokens_id'), 'refresh_tokens', ['id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_session_id'), 'refresh_tokens', ['session_id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_token_family_id'), 'refresh_tokens', ['token_family_id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_is_revoked'), 'refresh_tokens', ['is_revoked'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_created_at'), 'refresh_tokens', ['created_at'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_ip_address'), 'refresh_tokens', ['ip_address'], unique=False)
        
        logger.info("Created refresh_tokens table")
    else:
        logger.info("refresh_tokens table already exists")
    
    # Add refresh_token_family_id column to device_sessions if it doesn't exist
    if 'device_sessions' in tables:
        columns = [col['name'] for col in inspector.get_columns('device_sessions')]
        
        if 'refresh_token_family_id' not in columns:
            op.add_column(
                'device_sessions',
                sa.Column('refresh_token_family_id', sa.String(length=36), nullable=True)
            )
            op.create_index(
                op.f('ix_device_sessions_refresh_token_family_id'),
                'device_sessions',
                ['refresh_token_family_id'],
                unique=False
            )
            logger.info("Added refresh_token_family_id column to device_sessions table")
        else:
            logger.info("refresh_token_family_id column already exists in device_sessions table")
    else:
        logger.warning("device_sessions table not found - column will be added when table is created")


def downgrade() -> None:
    """
    Rollback dual-token strategy changes.
    Remove refresh_token_family_id column and drop refresh_tokens table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Remove refresh_token_family_id column from device_sessions
    if 'device_sessions' in tables:
        columns = [col['name'] for col in inspector.get_columns('device_sessions')]
        
        if 'refresh_token_family_id' in columns:
            # Drop index first
            try:
                op.drop_index(op.f('ix_device_sessions_refresh_token_family_id'), table_name='device_sessions')
            except Exception as e:
                logger.warning(f"Could not drop index: {e}")
            
            # Drop column
            op.drop_column('device_sessions', 'refresh_token_family_id')
            logger.info("Removed refresh_token_family_id column from device_sessions table")
    
    # Drop refresh_tokens table
    if 'refresh_tokens' in tables:
        op.drop_table('refresh_tokens')
        logger.info("Dropped refresh_tokens table")

