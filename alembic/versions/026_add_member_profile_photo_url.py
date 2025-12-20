"""add profile_photo_url to members table

Revision ID: 026_add_member_profile_photo_url
Revises: 025_rename_metadata_to_transfer_metadata
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "026_add_member_profile_photo_url"
down_revision = "025_rename_metadata_to_transfer_metadata"
branch_labels = None
depends_on = None


def upgrade():
    # Add profile_photo_url column to members table if it doesn't exist
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'members' in tables:
        members_columns = {col['name']: col for col in inspector.get_columns('members')}
        
        if 'profile_photo_url' not in members_columns:
            op.add_column('members', sa.Column('profile_photo_url', sa.String(500), nullable=True))


def downgrade():
    # Remove profile_photo_url column from members table
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'members' in tables:
        members_columns = {col['name']: col for col in inspector.get_columns('members')}
        
        if 'profile_photo_url' in members_columns:
            op.drop_column('members', 'profile_photo_url')

