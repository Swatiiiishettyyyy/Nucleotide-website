"""Remove member transfer system

Revision ID: 033_remove_member_transfer_system
Revises: 032_remove_unused_order_transfer_fields
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "033_remove_member_transfer_system"
down_revision = "032_remove_unused_order_transfer_fields"
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove member transfer system that is no longer used.
    Drops the member_transfer_logs table and all related indexes/constraints.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Drop member_transfer_logs table if it exists
    if 'member_transfer_logs' in inspector.get_table_names():
        # Drop indexes first
        try:
            op.drop_index('idx_member_transfer_logs_created_at', table_name='member_transfer_logs')
        except Exception:
            pass
        
        try:
            op.drop_index('idx_member_transfer_logs_phone', table_name='member_transfer_logs')
        except Exception:
            pass
        
        try:
            op.drop_index('idx_member_transfer_logs_status', table_name='member_transfer_logs')
        except Exception:
            pass
        
        try:
            op.drop_index('idx_member_transfer_logs_new_member', table_name='member_transfer_logs')
        except Exception:
            pass
        
        try:
            op.drop_index('idx_member_transfer_logs_old_member', table_name='member_transfer_logs')
        except Exception:
            pass
        
        try:
            op.drop_index('idx_member_transfer_logs_new_user', table_name='member_transfer_logs')
        except Exception:
            pass
        
        try:
            op.drop_index('idx_member_transfer_logs_old_user', table_name='member_transfer_logs')
        except Exception:
            pass
        
        # Drop foreign key constraints
        fks = inspector.get_foreign_keys('member_transfer_logs')
        for fk in fks:
            try:
                op.drop_constraint(fk['name'], 'member_transfer_logs', type_='foreignkey')
            except Exception:
                pass
        
        # Drop the table
        op.drop_table('member_transfer_logs')
        print("  - Dropped member_transfer_logs table")
    
    connection.commit()


def downgrade():
    """
    Re-create member_transfer_logs table (for rollback purposes).
    Note: This is unlikely to be needed as the transfer system is no longer used.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Re-create table if it doesn't exist
    if 'member_transfer_logs' not in inspector.get_table_names():
        op.create_table(
            'member_transfer_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('old_user_id', sa.Integer(), nullable=False),
            sa.Column('new_user_id', sa.Integer(), nullable=True),
            sa.Column('old_member_id', sa.Integer(), nullable=False),
            sa.Column('new_member_id', sa.Integer(), nullable=True),
            sa.Column('member_phone', sa.String(20), nullable=False),
            sa.Column('transfer_status', sa.String(20), nullable=False, server_default='PENDING_OTP'),
            sa.Column('otp_code', sa.String(10), nullable=True),
            sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('otp_verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('transfer_initiated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('transfer_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('initiated_by_user_id', sa.Integer(), nullable=True),
            sa.Column('cart_items_moved_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('consents_copied_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(50), nullable=True),
            sa.Column('user_agent', sa.String(500), nullable=True),
            sa.Column('correlation_id', sa.String(100), nullable=True),
            sa.Column('transfer_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create foreign keys
        op.create_foreign_key(
            'fk_member_transfer_logs_old_user',
            'member_transfer_logs', 'users',
            ['old_user_id'], ['id'],
            ondelete='CASCADE'
        )
        op.create_foreign_key(
            'fk_member_transfer_logs_new_user',
            'member_transfer_logs', 'users',
            ['new_user_id'], ['id'],
            ondelete='CASCADE'
        )
        op.create_foreign_key(
            'fk_member_transfer_logs_old_member',
            'member_transfer_logs', 'members',
            ['old_member_id'], ['id'],
            ondelete='RESTRICT'
        )
        op.create_foreign_key(
            'fk_member_transfer_logs_new_member',
            'member_transfer_logs', 'members',
            ['new_member_id'], ['id'],
            ondelete='RESTRICT'
        )
        op.create_foreign_key(
            'fk_member_transfer_logs_initiated_by',
            'member_transfer_logs', 'users',
            ['initiated_by_user_id'], ['id'],
            ondelete='SET NULL'
        )
        
        # Create indexes
        op.create_index('idx_member_transfer_logs_old_user', 'member_transfer_logs', ['old_user_id'])
        op.create_index('idx_member_transfer_logs_new_user', 'member_transfer_logs', ['new_user_id'])
        op.create_index('idx_member_transfer_logs_old_member', 'member_transfer_logs', ['old_member_id'])
        op.create_index('idx_member_transfer_logs_new_member', 'member_transfer_logs', ['new_member_id'])
        op.create_index('idx_member_transfer_logs_status', 'member_transfer_logs', ['transfer_status'])
        op.create_index('idx_member_transfer_logs_phone', 'member_transfer_logs', ['member_phone'])
        op.create_index('idx_member_transfer_logs_created_at', 'member_transfer_logs', ['created_at'])
        
        print("  - Re-created member_transfer_logs table")
    
    connection.commit()

