"""Add member dob and associated_category_id

Revision ID: 003_member_fields
Revises: 002_categories
Create Date: 2024-01-03 00:00:00.000000

Tags: members, categories
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_member_fields'
down_revision: Union[str, None] = '002_categories'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add dob and associated_category_id columns to members table.
    Backfills members with category references.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'members' not in inspector.get_table_names():
        return
    
    members_columns = {col['name'] for col in inspector.get_columns('members')}
    
    # Add dob column if it doesn't exist
    if 'dob' not in members_columns:
        op.add_column('members', sa.Column('dob', sa.Date(), nullable=True))
    
    # Add associated_category_id column if it doesn't exist
    if 'associated_category_id' not in members_columns:
        op.add_column('members', sa.Column('associated_category_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_members_associated_category_id'), 'members', ['associated_category_id'], unique=False)
        op.create_foreign_key('fk_members_associated_category_id', 'members', 'categories', ['associated_category_id'], ['id'])
        
        # Backfill members with category references
        from sqlalchemy import text
        
        # Get or create default category
        result = connection.execute(text("SELECT id FROM categories WHERE name = 'Genetic Testing' LIMIT 1"))
        default_category_id = result.scalar()
        
        if not default_category_id:
            dialect_name = connection.dialect.name
            if dialect_name == 'mysql':
                connection.execute(text("INSERT IGNORE INTO categories (name) VALUES ('Genetic Testing')"))
            else:
                connection.execute(text("""
                    INSERT INTO categories (name) VALUES ('Genetic Testing')
                    ON CONFLICT (name) DO NOTHING
                """))
            result = connection.execute(text("SELECT id FROM categories WHERE name = 'Genetic Testing' LIMIT 1"))
            default_category_id = result.scalar()
        
        if default_category_id:
            # Update members with NULL associated_category_id
            # Use associated_category name if available, otherwise use default
            connection.execute(text(f"""
                UPDATE members 
                SET associated_category_id = COALESCE(
                    (SELECT id FROM categories WHERE name = members.associated_category LIMIT 1),
                    {default_category_id}
                )
                WHERE associated_category_id IS NULL
            """))
            
            # Update associated_category field if it's NULL
            connection.execute(text(f"""
                UPDATE members 
                SET associated_category = 'Genetic Testing'
                WHERE associated_category IS NULL AND associated_category_id = {default_category_id}
            """))


def downgrade() -> None:
    """Remove member dob and associated_category_id"""
    op.drop_constraint('fk_members_associated_category_id', 'members', type_='foreignkey')
    op.drop_index(op.f('ix_members_associated_category_id'), table_name='members')
    op.drop_column('members', 'associated_category_id')
    op.drop_column('members', 'dob')

