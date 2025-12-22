"""add banners table

Revision ID: 029_add_banners_table
Revises: 028_remove_transfer_and_consent_fields
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '029_add_banners_table'
down_revision = '028_remove_transfer_and_consent_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Create banners table"""
    op.create_table(
        'banners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('subtitle', sa.String(length=500), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('action', sa.JSON(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_banners_id'), 'banners', ['id'], unique=False)
    op.create_index(op.f('ix_banners_position'), 'banners', ['position'], unique=False)
    op.create_index(op.f('ix_banners_is_active'), 'banners', ['is_active'], unique=False)
    op.create_index(op.f('ix_banners_start_date'), 'banners', ['start_date'], unique=False)
    op.create_index(op.f('ix_banners_end_date'), 'banners', ['end_date'], unique=False)
    op.create_index(op.f('ix_banners_is_deleted'), 'banners', ['is_deleted'], unique=False)


def downgrade():
    """Drop banners table"""
    op.drop_index(op.f('ix_banners_is_deleted'), table_name='banners')
    op.drop_index(op.f('ix_banners_end_date'), table_name='banners')
    op.drop_index(op.f('ix_banners_start_date'), table_name='banners')
    op.drop_index(op.f('ix_banners_is_active'), table_name='banners')
    op.drop_index(op.f('ix_banners_position'), table_name='banners')
    op.drop_index(op.f('ix_banners_id'), table_name='banners')
    op.drop_table('banners')

