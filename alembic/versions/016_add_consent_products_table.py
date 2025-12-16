"""Add consent_products table and update user_consents foreign key

Revision ID: 016_add_consent_products
Revises: 015_add_user_consents
Create Date: 2024-12-01 01:00:00.000000

Tags: consent, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '016_add_consent_products'
down_revision: Union[str, None] = '015_add_user_consents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create consent_products table and update user_consents to reference it.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Create consent_products table
    if 'consent_products' not in inspector.get_table_names():
        op.create_table(
            'consent_products',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes
        op.create_index('ix_consent_products_id', 'consent_products', ['id'], unique=False)
        op.create_index('ix_consent_products_name', 'consent_products', ['name'], unique=True)
        
        # Seed consent products
        # Insert "All Products" first (special product for login consent)
        connection.execute(
            sa.text("INSERT INTO consent_products (name) VALUES (:name)"),
            {"name": "All Products"}
        )
        
        # Insert other consent products
        consent_products = [
            "My genes",
            "Gut",
            "Biomarkers",
            "Multi-modal",
            "Donate sperm",
            "Donate egg",
            "Receive sperm",
            "Receive egg",
            "Family tree",
            "Family planning",
            "Child simulator",
            "IVF",
            "Life",
            "Health",
            "Fitness",
            "Nutrition",
            "Food"
        ]
        
        # Insert consent products
        for product_name in consent_products:
            connection.execute(
                sa.text("INSERT INTO consent_products (name) VALUES (:name)"),
                {"name": product_name}
            )
    
    # Update user_consents table foreign key if it exists
    if 'user_consents' in inspector.get_table_names():
        # Get existing foreign keys
        fk_constraints = [
            fk['name'] for fk in inspector.get_foreign_keys('user_consents')
            if 'product_id' in [col['name'] for col in fk.get('constrained_columns', [])]
        ]
        
        # Drop old foreign key if it exists
        for fk_name in fk_constraints:
            try:
                op.drop_constraint(fk_name, 'user_consents', type_='foreignkey')
            except Exception:
                pass
        
        # Add new foreign key to consent_products
        op.create_foreign_key(
            'fk_user_consents_consent_product',
            'user_consents',
            'consent_products',
            ['product_id'],
            ['id'],
            ondelete='CASCADE'
        )


def downgrade() -> None:
    """Revert by dropping consent_products and restoring old foreign key"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Update user_consents foreign key back to products if user_consents exists
    if 'user_consents' in inspector.get_table_names():
        # Drop new foreign key
        try:
            op.drop_constraint('fk_user_consents_consent_product', 'user_consents', type_='foreignkey')
        except Exception:
            pass
        
        # Restore old foreign key to products (if products table exists)
        if 'products' in inspector.get_table_names():
            try:
                op.create_foreign_key(
                    'fk_user_consents_product',
                    'user_consents',
                    'products',
                    ['product_id'],
                    ['ProductId'],
                    ondelete='CASCADE'
                )
            except Exception:
                pass
    
    # Drop consent_products table
    if 'consent_products' in inspector.get_table_names():
        op.drop_index('ix_consent_products_name', table_name='consent_products')
        op.drop_index('ix_consent_products_id', table_name='consent_products')
        op.drop_table('consent_products')

