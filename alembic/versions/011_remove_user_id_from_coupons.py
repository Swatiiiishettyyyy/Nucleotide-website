"""Remove user_id column from coupons table

Revision ID: 011_remove_coupon_user_id
Revises: 010_remove_cart_item_coupon
Create Date: 2024-11-27 18:00:00.000000

Tags: coupons
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011_remove_coupon_user_id'
down_revision: Union[str, None] = '010_remove_cart_item_coupon'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove user_id column from coupons table.
    Coupons are now applicable to all users (no user-specific coupons).
    Usage tracking is handled by cart_coupons table via max_uses limit.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'coupons' not in inspector.get_table_names():
        return
    
    coupons_columns = {col['name'] for col in inspector.get_columns('coupons')}
    
    # Drop user_id column if it exists
    if 'user_id' in coupons_columns:
        # Drop index first if it exists
        try:
            op.drop_index('ix_coupons_user_id', table_name='coupons')
        except Exception:
            # Index might not exist, continue
            pass
        
        # Drop foreign key constraint if it exists
        try:
            op.drop_constraint('coupons_ibfk_1', table_name='coupons', type_='foreignkey')
        except Exception:
            # Constraint might not exist or have different name, continue
            pass
        
        # Drop the column
        op.drop_column('coupons', 'user_id')


def downgrade() -> None:
    """Add user_id column back to coupons table (for rollback)"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'coupons' not in inspector.get_table_names():
        return
    
    coupons_columns = {col['name'] for col in inspector.get_columns('coupons')}
    
    # Add user_id column back if it doesn't exist
    if 'user_id' not in coupons_columns:
        op.add_column('coupons', sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_coupons_user_id'), 'coupons', ['user_id'], unique=False)
        op.create_foreign_key('coupons_ibfk_1', 'coupons', 'users', ['user_id'], ['id'], ondelete='CASCADE')

