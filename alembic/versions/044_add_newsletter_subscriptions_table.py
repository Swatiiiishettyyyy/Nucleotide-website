"""add newsletter subscriptions table

Revision ID: 044_add_newsletter_subscriptions_table
Revises: 043_increase_phone_number_column_sizes
Create Date: 2025-01-13 00:00:00.000000

Tags: newsletter, subscriptions, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '044_add_newsletter_subscriptions_table'
down_revision: Union[str, None] = '043_increase_phone_number_column_sizes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create newsletter_subscriptions table for storing newsletter email subscriptions.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if table already exists
    if 'newsletter_subscriptions' in inspector.get_table_names():
        return
    
    # Create newsletter_subscriptions table
    op.create_table(
        'newsletter_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('subscribed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes
    op.create_index(op.f('ix_newsletter_subscriptions_id'), 'newsletter_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_newsletter_subscriptions_email'), 'newsletter_subscriptions', ['email'], unique=False)
    op.create_index(op.f('ix_newsletter_subscriptions_user_id'), 'newsletter_subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_newsletter_subscriptions_is_active'), 'newsletter_subscriptions', ['is_active'], unique=False)
    op.create_index(op.f('ix_newsletter_subscriptions_subscribed_at'), 'newsletter_subscriptions', ['subscribed_at'], unique=False)
    
    # Create composite index for email and is_active
    op.create_index('idx_email_active', 'newsletter_subscriptions', ['email', 'is_active'], unique=False)


def downgrade() -> None:
    """Revert by dropping the newsletter_subscriptions table"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'newsletter_subscriptions' not in inspector.get_table_names():
        return
    
    # Drop indexes first
    op.drop_index('idx_email_active', table_name='newsletter_subscriptions')
    op.drop_index(op.f('ix_newsletter_subscriptions_subscribed_at'), table_name='newsletter_subscriptions')
    op.drop_index(op.f('ix_newsletter_subscriptions_is_active'), table_name='newsletter_subscriptions')
    op.drop_index(op.f('ix_newsletter_subscriptions_user_id'), table_name='newsletter_subscriptions')
    op.drop_index(op.f('ix_newsletter_subscriptions_email'), table_name='newsletter_subscriptions')
    op.drop_index(op.f('ix_newsletter_subscriptions_id'), table_name='newsletter_subscriptions')
    
    # Drop table
    op.drop_table('newsletter_subscriptions')

