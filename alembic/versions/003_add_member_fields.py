"""Add member dob

Revision ID: 003_member_fields
Revises: 002_categories
Create Date: 2024-01-03 00:00:00.000000

Tags: members
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
    Add dob column to members table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'members' not in inspector.get_table_names():
        return
    
    members_columns = {col['name'] for col in inspector.get_columns('members')}
    
    # Add dob column if it doesn't exist
    if 'dob' not in members_columns:
        op.add_column('members', sa.Column('dob', sa.Date(), nullable=True))
    

def downgrade() -> None:
    """Remove member dob"""
    op.drop_column('members', 'dob')

