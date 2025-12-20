"""add member transfer system

Revision ID: 021_add_member_transfer_system
Revises: 020_remove_member_transfer_fields
Create Date: 2025-01-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "021_add_member_transfer_system"
down_revision = "020_remove_member_transfer_fields"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ============================================
    # 1. Create member_transfer_logs table
    # ============================================
    tables = inspector.get_table_names()
    
    if 'member_transfer_logs' not in tables:
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
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['old_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['new_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['old_member_id'], ['members.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['new_member_id'], ['members.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['initiated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        )
        
        # Create indexes
        op.create_index('idx_member_transfer_logs_old_user', 'member_transfer_logs', ['old_user_id'])
        op.create_index('idx_member_transfer_logs_new_user', 'member_transfer_logs', ['new_user_id'])
        op.create_index('idx_member_transfer_logs_old_member', 'member_transfer_logs', ['old_member_id'])
        op.create_index('idx_member_transfer_logs_new_member', 'member_transfer_logs', ['new_member_id'])
        op.create_index('idx_member_transfer_logs_status', 'member_transfer_logs', ['transfer_status'])
        op.create_index('idx_member_transfer_logs_phone', 'member_transfer_logs', ['member_phone'])
        op.create_index('idx_member_transfer_logs_created_at', 'member_transfer_logs', ['created_at'])
    
    # ============================================
    # 2. Add transfer fields to members table
    # ============================================
    members_columns = {col['name']: col for col in inspector.get_columns('members')}
    
    if 'transferred_from_user_id' not in members_columns:
        op.add_column('members', sa.Column('transferred_from_user_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_members_transferred_from_user',
            'members', 'users',
            ['transferred_from_user_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index('idx_members_transferred_from_user', 'members', ['transferred_from_user_id'])
    
    if 'transfer_log_id' not in members_columns:
        op.add_column('members', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_members_transfer_log',
            'members', 'member_transfer_logs',
            ['transfer_log_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index('idx_members_transfer_log', 'members', ['transfer_log_id'])
    
    if 'is_self_profile' not in members_columns:
        op.add_column('members', sa.Column('is_self_profile', sa.Boolean(), nullable=False, server_default='0'))
        op.create_index('idx_members_is_self_profile', 'members', ['is_self_profile'])
    
    # ============================================
    # 3. Add transfer fields to orders table
    # ============================================
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    if 'linked_from_order_id' not in orders_columns:
        op.add_column('orders', sa.Column('linked_from_order_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_orders_linked_from_order',
            'orders', 'orders',
            ['linked_from_order_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'is_transferred_copy' not in orders_columns:
        op.add_column('orders', sa.Column('is_transferred_copy', sa.Boolean(), nullable=False, server_default='0'))
        op.create_index('idx_orders_is_transferred_copy', 'orders', ['is_transferred_copy'])
    
    if 'transfer_log_id' not in orders_columns:
        op.add_column('orders', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_orders_transfer_log',
            'orders', 'member_transfer_logs',
            ['transfer_log_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index('idx_orders_transfer_log', 'orders', ['transfer_log_id'])
    
    if 'transferred_at' not in orders_columns:
        op.add_column('orders', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # ============================================
    # 4. Add transfer fields to order_items table
    # ============================================
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    if 'linked_from_order_item_id' not in order_items_columns:
        op.add_column('order_items', sa.Column('linked_from_order_item_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_order_items_linked_from_order_item',
            'order_items', 'order_items',
            ['linked_from_order_item_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transfer_log_id' not in order_items_columns:
        op.add_column('order_items', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_order_items_transfer_log',
            'order_items', 'member_transfer_logs',
            ['transfer_log_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index('idx_order_items_transfer_log', 'order_items', ['transfer_log_id'])
    
    if 'transferred_at' not in order_items_columns:
        op.add_column('order_items', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # ============================================
    # 5. Add transfer fields to order_snapshots table
    # ============================================
    snapshots_columns = {col['name']: col for col in inspector.get_columns('order_snapshots')}
    
    if 'linked_from_snapshot_id' not in snapshots_columns:
        op.add_column('order_snapshots', sa.Column('linked_from_snapshot_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_order_snapshots_linked_from_snapshot',
            'order_snapshots', 'order_snapshots',
            ['linked_from_snapshot_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transfer_log_id' not in snapshots_columns:
        op.add_column('order_snapshots', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_order_snapshots_transfer_log',
            'order_snapshots', 'member_transfer_logs',
            ['transfer_log_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index('idx_order_snapshots_transfer_log', 'order_snapshots', ['transfer_log_id'])
    
    if 'transferred_at' not in snapshots_columns:
        op.add_column('order_snapshots', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # ============================================
    # 6. Add transfer fields to user_consents table
    # ============================================
    consents_columns = {col['name']: col for col in inspector.get_columns('user_consents')}
    
    if 'linked_from_consent_id' not in consents_columns:
        op.add_column('user_consents', sa.Column('linked_from_consent_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_user_consents_linked_from_consent',
            'user_consents', 'user_consents',
            ['linked_from_consent_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transfer_log_id' not in consents_columns:
        op.add_column('user_consents', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_user_consents_transfer_log',
            'user_consents', 'member_transfer_logs',
            ['transfer_log_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index('idx_user_consents_transfer_log', 'user_consents', ['transfer_log_id'])
    
    if 'transferred_at' not in consents_columns:
        op.add_column('user_consents', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Remove transfer fields from user_consents
    consents_columns = {col['name']: col for col in inspector.get_columns('user_consents')}
    if 'transferred_at' in consents_columns:
        op.drop_column('user_consents', 'transferred_at')
    if 'transfer_log_id' in consents_columns:
        try:
            op.drop_index('idx_user_consents_transfer_log', 'user_consents')
            op.drop_constraint('fk_user_consents_transfer_log', 'user_consents', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('user_consents', 'transfer_log_id')
    if 'linked_from_consent_id' in consents_columns:
        try:
            op.drop_constraint('fk_user_consents_linked_from_consent', 'user_consents', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('user_consents', 'linked_from_consent_id')
    
    # Remove transfer fields from order_snapshots
    snapshots_columns = {col['name']: col for col in inspector.get_columns('order_snapshots')}
    if 'transferred_at' in snapshots_columns:
        op.drop_column('order_snapshots', 'transferred_at')
    if 'transfer_log_id' in snapshots_columns:
        try:
            op.drop_index('idx_order_snapshots_transfer_log', 'order_snapshots')
            op.drop_constraint('fk_order_snapshots_transfer_log', 'order_snapshots', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('order_snapshots', 'transfer_log_id')
    if 'linked_from_snapshot_id' in snapshots_columns:
        try:
            op.drop_constraint('fk_order_snapshots_linked_from_snapshot', 'order_snapshots', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('order_snapshots', 'linked_from_snapshot_id')
    
    # Remove transfer fields from order_items
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    if 'transferred_at' in order_items_columns:
        op.drop_column('order_items', 'transferred_at')
    if 'transfer_log_id' in order_items_columns:
        try:
            op.drop_index('idx_order_items_transfer_log', 'order_items')
            op.drop_constraint('fk_order_items_transfer_log', 'order_items', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('order_items', 'transfer_log_id')
    if 'linked_from_order_item_id' in order_items_columns:
        try:
            op.drop_constraint('fk_order_items_linked_from_order_item', 'order_items', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('order_items', 'linked_from_order_item_id')
    
    # Remove transfer fields from orders
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    if 'transferred_at' in orders_columns:
        op.drop_column('orders', 'transferred_at')
    if 'transfer_log_id' in orders_columns:
        try:
            op.drop_index('idx_orders_transfer_log', 'orders')
            op.drop_constraint('fk_orders_transfer_log', 'orders', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('orders', 'transfer_log_id')
    if 'is_transferred_copy' in orders_columns:
        try:
            op.drop_index('idx_orders_is_transferred_copy', 'orders')
        except Exception:
            pass
        op.drop_column('orders', 'is_transferred_copy')
    if 'linked_from_order_id' in orders_columns:
        try:
            op.drop_constraint('fk_orders_linked_from_order', 'orders', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('orders', 'linked_from_order_id')
    
    # Remove transfer fields from members
    members_columns = {col['name']: col for col in inspector.get_columns('members')}
    if 'is_self_profile' in members_columns:
        try:
            op.drop_index('idx_members_is_self_profile', 'members')
        except Exception:
            pass
        op.drop_column('members', 'is_self_profile')
    if 'transfer_log_id' in members_columns:
        try:
            op.drop_index('idx_members_transfer_log', 'members')
            op.drop_constraint('fk_members_transfer_log', 'members', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('members', 'transfer_log_id')
    if 'transferred_from_user_id' in members_columns:
        try:
            op.drop_index('idx_members_transferred_from_user', 'members')
            op.drop_constraint('fk_members_transferred_from_user', 'members', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('members', 'transferred_from_user_id')
    
    # Drop member_transfer_logs table
    tables = inspector.get_table_names()
    if 'member_transfer_logs' in tables:
        try:
            op.drop_index('idx_member_transfer_logs_created_at', 'member_transfer_logs')
            op.drop_index('idx_member_transfer_logs_phone', 'member_transfer_logs')
            op.drop_index('idx_member_transfer_logs_status', 'member_transfer_logs')
            op.drop_index('idx_member_transfer_logs_new_member', 'member_transfer_logs')
            op.drop_index('idx_member_transfer_logs_old_member', 'member_transfer_logs')
            op.drop_index('idx_member_transfer_logs_new_user', 'member_transfer_logs')
            op.drop_index('idx_member_transfer_logs_old_user', 'member_transfer_logs')
            op.drop_constraint('fk_member_transfer_logs_initiated_by', 'member_transfer_logs', type_='foreignkey')
            op.drop_constraint('fk_member_transfer_logs_new_member', 'member_transfer_logs', type_='foreignkey')
            op.drop_constraint('fk_member_transfer_logs_old_member', 'member_transfer_logs', type_='foreignkey')
            op.drop_constraint('fk_member_transfer_logs_new_user', 'member_transfer_logs', type_='foreignkey')
            op.drop_constraint('fk_member_transfer_logs_old_user', 'member_transfer_logs', type_='foreignkey')
        except Exception:
            pass
        op.drop_table('member_transfer_logs')

