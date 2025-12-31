"""add_phone_change_tables

Revision ID: e644dba652bf
Revises: 14079edbe3a6
Create Date: 2025-12-26 18:22:36.297304

Tags: phone_change, authentication, security
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'e644dba652bf'
down_revision: Union[str, None] = '14079edbe3a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create phone_change_requests and phone_change_audit_logs tables
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Check if users table exists (required foreign key)
    if 'users' not in inspector.get_table_names():
        return  # Users table doesn't exist yet, skip migration
    
    # Step 1: Create phone_change_requests table
    if 'phone_change_requests' not in inspector.get_table_names():
        op.create_table(
            'phone_change_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('old_phone', sa.String(length=20), nullable=False),
            sa.Column('new_phone', sa.String(length=20), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='old_number_pending'),
            sa.Column('session_token', sa.String(length=100), nullable=True),
            sa.Column('old_phone_otp_attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('new_phone_otp_attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('sms_retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('old_phone_verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('new_phone_verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('session_token')
        )
        
        # Create indexes
        op.create_index('ix_phone_change_requests_id', 'phone_change_requests', ['id'])
        op.create_index('ix_phone_change_requests_user_id', 'phone_change_requests', ['user_id'])
        op.create_index('ix_phone_change_requests_status', 'phone_change_requests', ['status'])
        op.create_index('ix_phone_change_requests_session_token', 'phone_change_requests', ['session_token'], unique=True)
        op.create_index('ix_phone_change_requests_created_at', 'phone_change_requests', ['created_at'])
        op.create_index('ix_phone_change_requests_expires_at', 'phone_change_requests', ['expires_at'])
        op.create_index('ix_phone_change_requests_cooldown_until', 'phone_change_requests', ['cooldown_until'])
        op.create_index('ix_phone_change_requests_ip_address', 'phone_change_requests', ['ip_address'])
        
        # Create composite index for active requests per user
        op.create_index(
            'ix_user_status_active',
            'phone_change_requests',
            ['user_id', 'status', 'created_at']
        )
    
    # Step 2: Create phone_change_audit_logs table
    if 'phone_change_audit_logs' not in inspector.get_table_names():
        op.create_table(
            'phone_change_audit_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('request_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('success', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['request_id'], ['phone_change_requests.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes
        op.create_index('ix_phone_change_audit_logs_id', 'phone_change_audit_logs', ['id'])
        op.create_index('ix_phone_change_audit_logs_user_id', 'phone_change_audit_logs', ['user_id'])
        op.create_index('ix_phone_change_audit_logs_request_id', 'phone_change_audit_logs', ['request_id'])
        op.create_index('ix_phone_change_audit_logs_action', 'phone_change_audit_logs', ['action'])
        op.create_index('ix_phone_change_audit_logs_status', 'phone_change_audit_logs', ['status'])
        op.create_index('ix_phone_change_audit_logs_ip_address', 'phone_change_audit_logs', ['ip_address'])
        op.create_index('ix_phone_change_audit_logs_timestamp', 'phone_change_audit_logs', ['timestamp'])


def downgrade() -> None:
    """
    Drop phone_change_audit_logs and phone_change_requests tables
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Drop audit logs table first (due to foreign key)
    if 'phone_change_audit_logs' in inspector.get_table_names():
        op.drop_index('ix_phone_change_audit_logs_timestamp', table_name='phone_change_audit_logs')
        op.drop_index('ix_phone_change_audit_logs_ip_address', table_name='phone_change_audit_logs')
        op.drop_index('ix_phone_change_audit_logs_status', table_name='phone_change_audit_logs')
        op.drop_index('ix_phone_change_audit_logs_action', table_name='phone_change_audit_logs')
        op.drop_index('ix_phone_change_audit_logs_request_id', table_name='phone_change_audit_logs')
        op.drop_index('ix_phone_change_audit_logs_user_id', table_name='phone_change_audit_logs')
        op.drop_index('ix_phone_change_audit_logs_id', table_name='phone_change_audit_logs')
        op.drop_table('phone_change_audit_logs')
    
    # Drop phone change requests table
    if 'phone_change_requests' in inspector.get_table_names():
        op.drop_index('ix_user_status_active', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_ip_address', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_cooldown_until', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_expires_at', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_created_at', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_session_token', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_status', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_user_id', table_name='phone_change_requests')
        op.drop_index('ix_phone_change_requests_id', table_name='phone_change_requests')
        op.drop_table('phone_change_requests')
