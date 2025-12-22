"""Remove transfer_log_id, transferred_from_user_id, and login_consent_shown fields

Revision ID: 028_remove_transfer_and_consent_fields
Revises: 027_update_payment_status_enums
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '028_remove_transfer_and_consent_fields'
down_revision = '027_update_payment_status_enums'
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove the following fields from all tables:
    - login_consent_shown (from members table)
    - transferred_from_user_id (from members table)
    - transfer_log_id (from members, orders, order_items, order_snapshots, user_consents tables)
    
    Add the following field:
    - email (to members table, optional)
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if tables exist
    tables = inspector.get_table_names()
    if 'members' not in tables:
        return  # Tables don't exist yet, skip migration
    
    # ============================================
    # 1. Remove fields from members table
    # ============================================
    members_columns = {col['name']: col for col in inspector.get_columns('members')}
    
    # Remove login_consent_shown
    if 'login_consent_shown' in members_columns:
        try:
            op.drop_index('idx_members_login_consent_shown', 'members')
        except Exception:
            pass
        op.drop_column('members', 'login_consent_shown')
    
    # Remove transferred_from_user_id
    if 'transferred_from_user_id' in members_columns:
        try:
            op.drop_constraint('fk_members_transferred_from_user', 'members', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_index('idx_members_transferred_from_user', 'members')
        except Exception:
            pass
        op.drop_column('members', 'transferred_from_user_id')
    
    # Remove transfer_log_id
    if 'transfer_log_id' in members_columns:
        try:
            op.drop_constraint('fk_members_transfer_log', 'members', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_index('idx_members_transfer_log', 'members')
        except Exception:
            pass
        op.drop_column('members', 'transfer_log_id')
    
    # ============================================
    # 2. Remove transfer_log_id from orders table
    # ============================================
    if 'orders' in tables:
        orders_columns = {col['name']: col for col in inspector.get_columns('orders')}
        if 'transfer_log_id' in orders_columns:
            try:
                op.drop_constraint('fk_orders_transfer_log', 'orders', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_index('idx_orders_transfer_log', 'orders')
            except Exception:
                pass
            op.drop_column('orders', 'transfer_log_id')
    
    # ============================================
    # 3. Remove transfer_log_id from order_items table
    # ============================================
    if 'order_items' in tables:
        order_items_columns = {col['name']: col for col in inspector.get_columns('order_items')}
        if 'transfer_log_id' in order_items_columns:
            try:
                op.drop_constraint('fk_order_items_transfer_log', 'order_items', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_index('idx_order_items_transfer_log', 'order_items')
            except Exception:
                pass
            op.drop_column('order_items', 'transfer_log_id')
    
    # ============================================
    # 4. Remove transfer_log_id from order_snapshots table
    # ============================================
    if 'order_snapshots' in tables:
        snapshots_columns = {col['name']: col for col in inspector.get_columns('order_snapshots')}
        if 'transfer_log_id' in snapshots_columns:
            try:
                op.drop_constraint('fk_order_snapshots_transfer_log', 'order_snapshots', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_index('idx_order_snapshots_transfer_log', 'order_snapshots')
            except Exception:
                pass
            op.drop_column('order_snapshots', 'transfer_log_id')
    
    # ============================================
    # 5. Remove transfer_log_id from user_consents table
    # ============================================
    if 'user_consents' in tables:
        consents_columns = {col['name']: col for col in inspector.get_columns('user_consents')}
        if 'transfer_log_id' in consents_columns:
            try:
                op.drop_constraint('fk_user_consents_transfer_log', 'user_consents', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_index('idx_user_consents_transfer_log', 'user_consents')
            except Exception:
                pass
            op.drop_column('user_consents', 'transfer_log_id')
    
    # ============================================
    # 6. Add email field to members table
    # ============================================
    members_columns_after = {col['name']: col for col in inspector.get_columns('members')}
    if 'email' not in members_columns_after:
        op.add_column('members', sa.Column('email', sa.String(255), nullable=True))


def downgrade():
    """
    Re-add the removed fields (reverse of upgrade).
    Note: This is a simplified downgrade - full restoration would require
    recreating all the exact constraints and indexes.
    """
    # Re-add members table fields
    op.add_column('members', sa.Column('login_consent_shown', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('members', sa.Column('transferred_from_user_id', sa.Integer(), nullable=True))
    op.add_column('members', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
    
    # Re-add orders table field
    op.add_column('orders', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
    
    # Re-add order_items table field
    op.add_column('order_items', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
    
    # Re-add order_snapshots table field
    op.add_column('order_snapshots', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
    
    # Re-add user_consents table field
    op.add_column('user_consents', sa.Column('transfer_log_id', sa.Integer(), nullable=True))
    
    # Remove email field from members table
    op.drop_column('members', 'email')

