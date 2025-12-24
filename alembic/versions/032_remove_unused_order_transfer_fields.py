"""Remove unused order and consent transfer fields

Revision ID: 032_remove_unused_order_transfer_fields
Revises: 031_add_cart_item_soft_delete
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "032_remove_unused_order_transfer_fields"
down_revision = "031_add_cart_item_soft_delete"
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove unused order and consent transfer fields.
    - Order transfer fields were added for functionality that was never implemented.
    - Consent transfer fields are no longer needed as transfer tracking is not required.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ============================================
    # 1. Remove transfer fields from orders table
    # ============================================
    if 'orders' in inspector.get_table_names():
        orders_columns = {col['name'] for col in inspector.get_columns('orders')}
        
        # Drop index first if it exists
        if 'is_transferred_copy' in orders_columns:
            try:
                op.drop_index('idx_orders_is_transferred_copy', table_name='orders')
            except Exception:
                pass  # Index might not exist
        
        # Drop foreign key constraint if it exists
        orders_fks = inspector.get_foreign_keys('orders')
        for fk in orders_fks:
            if 'linked_from_order_id' in fk.get('constrained_columns', []):
                try:
                    op.drop_constraint(fk['name'], 'orders', type_='foreignkey')
                except Exception:
                    pass
        
        # Drop columns
        if 'linked_from_order_id' in orders_columns:
            op.drop_column('orders', 'linked_from_order_id')
            print("  - Removed linked_from_order_id from orders")
        
        if 'is_transferred_copy' in orders_columns:
            op.drop_column('orders', 'is_transferred_copy')
            print("  - Removed is_transferred_copy from orders")
        
        if 'transferred_at' in orders_columns:
            op.drop_column('orders', 'transferred_at')
            print("  - Removed transferred_at from orders")
    
    # ============================================
    # 2. Remove transfer fields from order_items table
    # ============================================
    if 'order_items' in inspector.get_table_names():
        order_items_columns = {col['name'] for col in inspector.get_columns('order_items')}
        
        # Drop foreign key constraint if it exists
        order_items_fks = inspector.get_foreign_keys('order_items')
        for fk in order_items_fks:
            if 'linked_from_order_item_id' in fk.get('constrained_columns', []):
                try:
                    op.drop_constraint(fk['name'], 'order_items', type_='foreignkey')
                except Exception:
                    pass
        
        # Drop columns
        if 'linked_from_order_item_id' in order_items_columns:
            op.drop_column('order_items', 'linked_from_order_item_id')
            print("  - Removed linked_from_order_item_id from order_items")
        
        if 'transferred_at' in order_items_columns:
            op.drop_column('order_items', 'transferred_at')
            print("  - Removed transferred_at from order_items")
    
    # ============================================
    # 3. Remove transfer fields from order_snapshots table
    # ============================================
    if 'order_snapshots' in inspector.get_table_names():
        snapshots_columns = {col['name'] for col in inspector.get_columns('order_snapshots')}
        
        # Drop foreign key constraint if it exists
        snapshots_fks = inspector.get_foreign_keys('order_snapshots')
        for fk in snapshots_fks:
            if 'linked_from_snapshot_id' in fk.get('constrained_columns', []):
                try:
                    op.drop_constraint(fk['name'], 'order_snapshots', type_='foreignkey')
                except Exception:
                    pass
        
        # Drop columns
        if 'linked_from_snapshot_id' in snapshots_columns:
            op.drop_column('order_snapshots', 'linked_from_snapshot_id')
            print("  - Removed linked_from_snapshot_id from order_snapshots")
        
        if 'transferred_at' in snapshots_columns:
            op.drop_column('order_snapshots', 'transferred_at')
            print("  - Removed transferred_at from order_snapshots")
    
    # ============================================
    # 4. Remove transfer fields from user_consents table
    # ============================================
    if 'user_consents' in inspector.get_table_names():
        consents_columns = {col['name'] for col in inspector.get_columns('user_consents')}
        
        # Drop foreign key constraint if it exists
        consents_fks = inspector.get_foreign_keys('user_consents')
        for fk in consents_fks:
            if 'linked_from_consent_id' in fk.get('constrained_columns', []):
                try:
                    op.drop_constraint(fk['name'], 'user_consents', type_='foreignkey')
                except Exception:
                    pass
        
        # Drop columns
        if 'linked_from_consent_id' in consents_columns:
            op.drop_column('user_consents', 'linked_from_consent_id')
            print("  - Removed linked_from_consent_id from user_consents")
        
        if 'transferred_at' in consents_columns:
            op.drop_column('user_consents', 'transferred_at')
            print("  - Removed transferred_at from user_consents")
    
    connection.commit()


def downgrade():
    """
    Re-add the order and consent transfer fields (for rollback purposes).
    Note: This is unlikely to be needed as these fields were not used or are no longer needed.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Re-add fields to orders table
    if 'orders' in inspector.get_table_names():
        orders_columns = {col['name'] for col in inspector.get_columns('orders')}
        
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
        
        if 'transferred_at' not in orders_columns:
            op.add_column('orders', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Re-add fields to order_items table
    if 'order_items' in inspector.get_table_names():
        order_items_columns = {col['name'] for col in inspector.get_columns('order_items')}
        
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
    
    # Re-add fields to order_snapshots table
    if 'order_snapshots' in inspector.get_table_names():
        snapshots_columns = {col['name'] for col in inspector.get_columns('order_snapshots')}
        
        if 'linked_from_snapshot_id' not in snapshots_columns:
            op.add_column('order_snapshots', sa.Column('linked_from_snapshot_id', sa.Integer(), nullable=True))
            op.create_foreign_key(
                'fk_order_snapshots_linked_from_snapshot',
                'order_snapshots', 'order_snapshots',
                ['linked_from_snapshot_id'], ['id'],
                ondelete='SET NULL'
            )
        
        if 'transferred_at' not in snapshots_columns:
            op.add_column('order_snapshots', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    # Re-add fields to user_consents table
    if 'user_consents' in inspector.get_table_names():
        consents_columns = {col['name'] for col in inspector.get_columns('user_consents')}
        
        if 'linked_from_consent_id' not in consents_columns:
            op.add_column('user_consents', sa.Column('linked_from_consent_id', sa.Integer(), nullable=True))
            op.create_foreign_key(
                'fk_user_consents_linked_from_consent',
                'user_consents', 'user_consents',
                ['linked_from_consent_id'], ['id'],
                ondelete='SET NULL'
            )
        
        if 'transferred_at' not in consents_columns:
            op.add_column('user_consents', sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True))
    
    connection.commit()

