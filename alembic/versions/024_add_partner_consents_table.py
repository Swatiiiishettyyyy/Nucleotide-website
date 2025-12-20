"""add partner consents table for product 11

Revision ID: 024_add_partner_consents_table
Revises: 023_add_profile_photo_url
Create Date: 2025-01-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "024_add_partner_consents_table"
down_revision = "023_add_profile_photo_url"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'partner_consents' not in tables:
        op.create_table(
            'partner_consents',
            sa.Column('id', sa.Integer(), nullable=False),
            
            # Product info
            sa.Column('product_id', sa.Integer(), nullable=False),
            
            # User (requester) info
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('user_member_id', sa.Integer(), nullable=False),
            sa.Column('user_name', sa.String(100), nullable=False),
            sa.Column('user_mobile', sa.String(20), nullable=False),
            sa.Column('user_consent', sa.String(10), nullable=False, server_default='no'),
            
            # Partner info
            sa.Column('partner_user_id', sa.Integer(), nullable=True),
            sa.Column('partner_member_id', sa.Integer(), nullable=True),
            sa.Column('partner_name', sa.String(100), nullable=True),
            sa.Column('partner_mobile', sa.String(20), nullable=False),
            sa.Column('partner_consent', sa.String(10), nullable=False, server_default='no'),
            
            # Final status
            sa.Column('final_status', sa.String(10), nullable=False, server_default='no'),
            
            # Metadata
            sa.Column('consent_source', sa.String(20), nullable=False, server_default='product'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['product_id'], ['consent_products.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_member_id'], ['members.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['partner_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['partner_member_id'], ['members.id'], ondelete='SET NULL'),
        )
        
        # Create indexes
        op.create_index('ix_partner_consents_id', 'partner_consents', ['id'], unique=False)
        op.create_index('ix_partner_consents_product_id', 'partner_consents', ['product_id'], unique=False)
        op.create_index('ix_partner_consents_user_id', 'partner_consents', ['user_id'], unique=False)
        op.create_index('ix_partner_consents_user_member_id', 'partner_consents', ['user_member_id'], unique=False)
        op.create_index('ix_partner_consents_user_mobile', 'partner_consents', ['user_mobile'], unique=False)
        op.create_index('ix_partner_consents_partner_user_id', 'partner_consents', ['partner_user_id'], unique=False)
        op.create_index('ix_partner_consents_partner_member_id', 'partner_consents', ['partner_member_id'], unique=False)
        op.create_index('ix_partner_consents_partner_mobile', 'partner_consents', ['partner_mobile'], unique=False)
        op.create_index('idx_user_member_product', 'partner_consents', ['user_member_id', 'product_id'], unique=True)


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'partner_consents' in tables:
        # Drop indexes first
        try:
            op.drop_index('idx_user_member_product', table_name='partner_consents')
            op.drop_index('ix_partner_consents_partner_mobile', table_name='partner_consents')
            op.drop_index('ix_partner_consents_partner_member_id', table_name='partner_consents')
            op.drop_index('ix_partner_consents_partner_user_id', table_name='partner_consents')
            op.drop_index('ix_partner_consents_user_mobile', table_name='partner_consents')
            op.drop_index('ix_partner_consents_user_member_id', table_name='partner_consents')
            op.drop_index('ix_partner_consents_user_id', table_name='partner_consents')
            op.drop_index('ix_partner_consents_product_id', table_name='partner_consents')
            op.drop_index('ix_partner_consents_id', table_name='partner_consents')
        except Exception:
            pass
        
        op.drop_table('partner_consents')

