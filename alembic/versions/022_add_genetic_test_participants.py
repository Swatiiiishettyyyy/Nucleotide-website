"""add genetic test participants table

Revision ID: 022_add_genetic_test_participants
Revises: 021_add_member_transfer_system
Create Date: 2025-01-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "022_add_genetic_test_participants"
down_revision = "021_add_member_transfer_system"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ============================================
    # Create genetic_test_participants table
    # ============================================
    tables = inspector.get_table_names()
    
    if 'genetic_test_participants' not in tables:
        op.create_table(
            'genetic_test_participants',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('member_id', sa.Integer(), nullable=False),
            sa.Column('mobile', sa.String(20), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('has_taken_genetic_test', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('plan_type', sa.String(50), nullable=True),
            sa.Column('product_id', sa.Integer(), nullable=True),
            sa.Column('category_id', sa.Integer(), nullable=True),
            sa.Column('order_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('member_id', name='uq_genetic_test_participants_member_id'),  # One record per member
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['product_id'], ['products.ProductId'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL')
        )
        
        # Create indexes
        op.create_index(op.f('ix_genetic_test_participants_id'), 'genetic_test_participants', ['id'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_user_id'), 'genetic_test_participants', ['user_id'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_member_id'), 'genetic_test_participants', ['member_id'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_mobile'), 'genetic_test_participants', ['mobile'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_has_taken_genetic_test'), 'genetic_test_participants', ['has_taken_genetic_test'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_plan_type'), 'genetic_test_participants', ['plan_type'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_product_id'), 'genetic_test_participants', ['product_id'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_category_id'), 'genetic_test_participants', ['category_id'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_order_id'), 'genetic_test_participants', ['order_id'], unique=False)
        op.create_index(op.f('ix_genetic_test_participants_created_at'), 'genetic_test_participants', ['created_at'], unique=False)


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    tables = inspector.get_table_names()
    
    if 'genetic_test_participants' in tables:
        # Drop unique constraint first
        try:
            op.drop_constraint('uq_genetic_test_participants_member_id', 'genetic_test_participants', type_='unique')
        except Exception:
            pass
        
        op.drop_index(op.f('ix_genetic_test_participants_created_at'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_order_id'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_category_id'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_product_id'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_plan_type'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_has_taken_genetic_test'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_mobile'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_member_id'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_user_id'), table_name='genetic_test_participants')
        op.drop_index(op.f('ix_genetic_test_participants_id'), table_name='genetic_test_participants')
        op.drop_table('genetic_test_participants')

