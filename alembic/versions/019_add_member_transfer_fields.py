"""add member transfer fields

Revision ID: 019_add_member_transfer_fields
Revises: 018_add_member_scoped_consent
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "019_add_member_transfer_fields"
down_revision = "018_add_member_scoped_consent"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ============================================
    # 1. Add transfer fields to members table
    # ============================================
    members_columns = {col['name']: col for col in inspector.get_columns('members')}
    
    if 'is_transferred' not in members_columns:
        op.add_column('members', sa.Column('is_transferred', sa.Boolean(), nullable=False, server_default='0'))
    
    if 'transferred_to_user_id' not in members_columns:
        op.add_column('members', sa.Column('transferred_to_user_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_members_transferred_to_user',
            'members', 'users',
            ['transferred_to_user_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transferred_to_member_id' not in members_columns:
        op.add_column('members', sa.Column('transferred_to_member_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_members_transferred_to_member',
            'members', 'members',
            ['transferred_to_member_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transferred_at' not in members_columns:
        op.add_column('members', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    if 'linked_from_member_id' not in members_columns:
        op.add_column('members', sa.Column('linked_from_member_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_members_linked_from_member',
            'members', 'members',
            ['linked_from_member_id'], ['id'],
            ondelete='SET NULL'
        )
    
    # Create indexes for transfer fields
    try:
        op.create_index('idx_members_is_transferred', 'members', ['is_transferred'])
        op.create_index('idx_members_transferred_to_user', 'members', ['transferred_to_user_id'])
    except Exception:
        pass  # Index might already exist
    
    # ============================================
    # 2. Add transfer fields to orders table
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
    
    if 'transferred_at' not in orders_columns:
        op.add_column('orders', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Create index
    try:
        op.create_index('idx_orders_is_transferred_copy', 'orders', ['is_transferred_copy'])
    except Exception:
        pass
    
    # ============================================
    # 3. Add transfer fields to order_items table
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
    
    if 'transferred_at' not in order_items_columns:
        op.add_column('order_items', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # ============================================
    # 4. Add transfer fields to cart_items table
    # ============================================
    cart_items_columns = {col['name']: col for col in inspector.get_columns('cart_items')}
    
    if 'linked_from_cart_item_id' not in cart_items_columns:
        op.add_column('cart_items', sa.Column('linked_from_cart_item_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_cart_items_linked_from_cart_item',
            'cart_items', 'cart_items',
            ['linked_from_cart_item_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transferred_at' not in cart_items_columns:
        op.add_column('cart_items', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # ============================================
    # 5. Add transfer fields to user_consents table
    # ============================================
    user_consents_columns = {col['name']: col for col in inspector.get_columns('user_consents')}
    
    if 'linked_from_consent_id' not in user_consents_columns:
        op.add_column('user_consents', sa.Column('linked_from_consent_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_user_consents_linked_from_consent',
            'user_consents', 'user_consents',
            ['linked_from_consent_id'], ['id'],
            ondelete='SET NULL'
        )
    
    if 'transferred_at' not in user_consents_columns:
        op.add_column('user_consents', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # ============================================
    # 6. Create member_transfers table
    # ============================================
    tables = inspector.get_table_names()
    
    if 'member_transfers' not in tables:
        op.create_table(
            'member_transfers',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('old_user_id', sa.Integer(), nullable=False),
            sa.Column('new_user_id', sa.Integer(), nullable=False),
            sa.Column('old_member_id', sa.Integer(), nullable=False),
            sa.Column('new_member_id', sa.Integer(), nullable=False),
            sa.Column('transferred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('transferred_by', sa.String(50), nullable=False, server_default='system'),
            sa.Column('status', sa.String(20), nullable=False, server_default='completed'),
            sa.Column('orders_copied', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('order_items_copied', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cart_items_copied', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('consent_records_copied', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(50), nullable=True),
            sa.Column('user_agent', sa.String(500), nullable=True),
            sa.Column('correlation_id', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['old_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['new_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['old_member_id'], ['members.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['new_member_id'], ['members.id'], ondelete='CASCADE'),
        )
        
        # Create indexes
        op.create_index('idx_member_transfers_old_user', 'member_transfers', ['old_user_id'])
        op.create_index('idx_member_transfers_new_user', 'member_transfers', ['new_user_id'])
        op.create_index('idx_member_transfers_old_member', 'member_transfers', ['old_member_id'])
        op.create_index('idx_member_transfers_new_member', 'member_transfers', ['new_member_id'])
        op.create_index('idx_member_transfers_status', 'member_transfers', ['status'])
        op.create_index('idx_member_transfers_transferred_at', 'member_transfers', ['transferred_at'])


def downgrade():
    # Drop member_transfers table
    op.drop_table('member_transfers')
    
    # Remove transfer fields from user_consents
    op.drop_column('user_consents', 'transferred_at')
    op.drop_column('user_consents', 'linked_from_consent_id')
    
    # Remove transfer fields from cart_items
    op.drop_column('cart_items', 'transferred_at')
    op.drop_column('cart_items', 'linked_from_cart_item_id')
    
    # Remove transfer fields from order_items
    op.drop_column('order_items', 'transferred_at')
    op.drop_column('order_items', 'linked_from_order_item_id')
    
    # Remove transfer fields from orders
    op.drop_column('orders', 'transferred_at')
    op.drop_column('orders', 'is_transferred_copy')
    op.drop_column('orders', 'linked_from_order_id')
    
    # Remove transfer fields from members
    op.drop_column('members', 'linked_from_member_id')
    op.drop_column('members', 'transferred_at')
    op.drop_column('members', 'transferred_to_member_id')
    op.drop_column('members', 'transferred_to_user_id')
    op.drop_column('members', 'is_transferred')

