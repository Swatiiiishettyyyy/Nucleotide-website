"""remove member transfer fields

Revision ID: 020_remove_member_transfer_fields
Revises: 019_add_member_transfer_fields
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "020_remove_member_transfer_fields"
down_revision = "019_add_member_transfer_fields"
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove all member transfer functionality:
    - Drop member_transfers table
    - Remove transfer fields from all tables
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ============================================
    # 1. Drop member_transfers table
    # ============================================
    tables = inspector.get_table_names()
    if 'member_transfers' in tables:
        # Drop foreign keys first
        try:
            op.drop_constraint('fk_member_transfers_old_user', 'member_transfers', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_constraint('fk_member_transfers_new_user', 'member_transfers', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_constraint('fk_member_transfers_old_member', 'member_transfers', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_constraint('fk_member_transfers_new_member', 'member_transfers', type_='foreignkey')
        except Exception:
            pass
        
        # Drop indexes
        try:
            op.drop_index('idx_member_transfers_old_user', 'member_transfers')
        except Exception:
            pass
        try:
            op.drop_index('idx_member_transfers_new_user', 'member_transfers')
        except Exception:
            pass
        try:
            op.drop_index('idx_member_transfers_old_member', 'member_transfers')
        except Exception:
            pass
        try:
            op.drop_index('idx_member_transfers_new_member', 'member_transfers')
        except Exception:
            pass
        try:
            op.drop_index('idx_member_transfers_status', 'member_transfers')
        except Exception:
            pass
        try:
            op.drop_index('idx_member_transfers_transferred_at', 'member_transfers')
        except Exception:
            pass
        
        # Drop table
        op.drop_table('member_transfers')
    
    # ============================================
    # 2. Remove transfer fields from user_consents table
    # ============================================
    user_consents_columns = {col['name']: col for col in inspector.get_columns('user_consents')}
    
    if 'transferred_at' in user_consents_columns:
        op.drop_column('user_consents', 'transferred_at')
    
    if 'linked_from_consent_id' in user_consents_columns:
        try:
            op.drop_constraint('fk_user_consents_linked_from_consent', 'user_consents', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('user_consents', 'linked_from_consent_id')
    
    # ============================================
    # 3. Remove transfer fields from cart_items table
    # ============================================
    cart_items_columns = {col['name']: col for col in inspector.get_columns('cart_items')}
    
    if 'transferred_at' in cart_items_columns:
        op.drop_column('cart_items', 'transferred_at')
    
    if 'linked_from_cart_item_id' in cart_items_columns:
        try:
            op.drop_constraint('fk_cart_items_linked_from_cart_item', 'cart_items', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('cart_items', 'linked_from_cart_item_id')
    
    # ============================================
    # 4. Remove transfer fields from order_items table
    # ============================================
    order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
    
    if 'transferred_at' in order_items_columns:
        op.drop_column('order_items', 'transferred_at')
    
    if 'linked_from_order_item_id' in order_items_columns:
        try:
            op.drop_constraint('fk_order_items_linked_from_order_item', 'order_items', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('order_items', 'linked_from_order_item_id')
    
    # ============================================
    # 5. Remove transfer fields from orders table
    # ============================================
    orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    if 'transferred_at' in orders_columns:
        op.drop_column('orders', 'transferred_at')
    
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
    
    # ============================================
    # 6. Remove transfer fields from members table
    # ============================================
    members_columns = {col['name']: col for col in inspector.get_columns('members')}
    
    if 'linked_from_member_id' in members_columns:
        try:
            op.drop_constraint('fk_members_linked_from_member', 'members', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('members', 'linked_from_member_id')
    
    if 'transferred_at' in members_columns:
        op.drop_column('members', 'transferred_at')
    
    if 'transferred_to_member_id' in members_columns:
        try:
            op.drop_constraint('fk_members_transferred_to_member', 'members', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('members', 'transferred_to_member_id')
    
    if 'transferred_to_user_id' in members_columns:
        try:
            op.drop_constraint('fk_members_transferred_to_user', 'members', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_index('idx_members_transferred_to_user', 'members')
        except Exception:
            pass
        op.drop_column('members', 'transferred_to_user_id')
    
    if 'is_transferred' in members_columns:
        try:
            op.drop_index('idx_members_is_transferred', 'members')
        except Exception:
            pass
        op.drop_column('members', 'is_transferred')


def downgrade():
    """
    Re-add member transfer fields (reverse of upgrade).
    Note: This is a simplified downgrade - full restoration would require
    recreating all the exact constraints and indexes from migration 019.
    """
    # Re-add members table fields
    op.add_column('members', sa.Column('is_transferred', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('members', sa.Column('transferred_to_user_id', sa.Integer(), nullable=True))
    op.add_column('members', sa.Column('transferred_to_member_id', sa.Integer(), nullable=True))
    op.add_column('members', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('members', sa.Column('linked_from_member_id', sa.Integer(), nullable=True))
    
    # Re-add orders table fields
    op.add_column('orders', sa.Column('linked_from_order_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('is_transferred_copy', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Re-add order_items table fields
    op.add_column('order_items', sa.Column('linked_from_order_item_id', sa.Integer(), nullable=True))
    op.add_column('order_items', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Re-add cart_items table fields
    op.add_column('cart_items', sa.Column('linked_from_cart_item_id', sa.Integer(), nullable=True))
    op.add_column('cart_items', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Re-add user_consents table fields
    op.add_column('user_consents', sa.Column('linked_from_consent_id', sa.Integer(), nullable=True))
    op.add_column('user_consents', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Re-create member_transfers table
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
    )










