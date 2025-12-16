"""Add user_consents table

Revision ID: 015_add_user_consents
Revises: 014_remove_order_item_price_fields
Create Date: 2024-12-01 00:00:00.000000

Tags: consent, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '015_add_user_consents'
down_revision: Union[str, None] = '014_remove_order_item_price_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create user_consents table for storing user consent records.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if table already exists
    if 'user_consents' in inspector.get_table_names():
        return
    
    # Create user_consents table
    op.create_table(
        'user_consents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_phone', sa.String(length=20), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('consent_given', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('consent_source', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='yes'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['consent_products.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('ix_user_consents_id', 'user_consents', ['id'], unique=False)
    op.create_index('ix_user_consents_user_id', 'user_consents', ['user_id'], unique=False)
    op.create_index('ix_user_consents_user_phone', 'user_consents', ['user_phone'], unique=False)
    op.create_index('ix_user_consents_product_id', 'user_consents', ['product_id'], unique=False)
    
    # Create composite unique index to prevent duplicates
    op.create_index('idx_user_phone_product', 'user_consents', ['user_phone', 'product_id'], unique=True)


def downgrade() -> None:
    """Revert by dropping the user_consents table"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'user_consents' not in inspector.get_table_names():
        return
    
    # Drop indexes first
    op.drop_index('idx_user_phone_product', table_name='user_consents')
    op.drop_index('ix_user_consents_product_id', table_name='user_consents')
    op.drop_index('ix_user_consents_user_phone', table_name='user_consents')
    op.drop_index('ix_user_consents_user_id', table_name='user_consents')
    op.drop_index('ix_user_consents_id', table_name='user_consents')
    
    # Drop table
    op.drop_table('user_consents')

