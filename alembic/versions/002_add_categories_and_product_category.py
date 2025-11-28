"""Add categories table and product category_id

Revision ID: 002_categories
Revises: 001_initial
Create Date: 2024-01-02 00:00:00.000000

Tags: categories, products
"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_categories'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add categories table and category_id column to products.
    Backfills products with default category.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Create categories table if it doesn't exist
    if 'categories' not in inspector.get_table_names():
        op.create_table(
            'categories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_categories_id'), 'categories', ['id'], unique=False)
        op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True)
    
    # Create products table if it doesn't exist
    if 'products' not in inspector.get_table_names():
        # Import Product model to get table structure
        import sys
        from pathlib import Path
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        
        from Product_module.Product_model import Product
        from database import Base
        
        # Create products table using Base.metadata
        Product.__table__.create(bind=connection, checkfirst=True)
        logger = logging.getLogger(__name__)
        logger.info("Created products table")
    
    # Add category_id to products table if it doesn't exist
    if 'products' in inspector.get_table_names():
        products_columns = {col['name'] for col in inspector.get_columns('products')}
        
        if 'category_id' not in products_columns:
            op.add_column('products', sa.Column('category_id', sa.Integer(), nullable=True))
            op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)
            
            # Create default category and backfill products
            from sqlalchemy import text
            
            # Insert default category if it doesn't exist (database-agnostic)
            if dialect_name == 'mysql':
                connection.execute(text("""
                    INSERT IGNORE INTO categories (name) 
                    VALUES ('Genetic Testing')
                """))
            elif dialect_name == 'postgresql':
                # PostgreSQL syntax
                connection.execute(text("""
                    INSERT INTO categories (name) 
                    VALUES ('Genetic Testing')
                    ON CONFLICT (name) DO NOTHING
                """))
            else:
                # SQLite and others - check first, then insert
                result = connection.execute(text("SELECT COUNT(*) FROM categories WHERE name = 'Genetic Testing'"))
                if result.scalar() == 0:
                    connection.execute(text("""
                        INSERT INTO categories (name) 
                        VALUES ('Genetic Testing')
                    """))
            
            # Get default category ID and update products
            result = connection.execute(text("SELECT id FROM categories WHERE name = 'Genetic Testing' LIMIT 1"))
            default_category_id = result.scalar()
            
            if default_category_id:
                # Update products with NULL category_id to use default
                connection.execute(text(f"""
                    UPDATE products 
                    SET category_id = {default_category_id} 
                    WHERE category_id IS NULL
                """))
            
            # Add foreign key constraint
            op.create_foreign_key('fk_products_category_id', 'products', 'categories', ['category_id'], ['id'])
            
            # Make category_id NOT NULL after backfill
            op.alter_column('products', 'category_id', nullable=False)


def downgrade() -> None:
    """Remove categories table and product category_id"""
    op.drop_constraint('fk_products_category_id', 'products', type_='foreignkey')
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.drop_column('products', 'category_id')
    op.drop_index(op.f('ix_categories_name'), table_name='categories')
    op.drop_index(op.f('ix_categories_id'), table_name='categories')
    op.drop_table('categories')

