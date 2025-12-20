"""add profile_photo_url to users table

Revision ID: 023_add_profile_photo_url
Revises: 022_add_genetic_test_participants
Create Date: 2025-01-17
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "023_add_profile_photo_url"
down_revision = "022_add_genetic_test_participants"
branch_labels = None
depends_on = None


def upgrade():
    # Add profile_photo_url column to users table if it doesn't exist
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    users_columns = {col['name']: col for col in inspector.get_columns('users')}
    
    if 'profile_photo_url' not in users_columns:
        op.add_column('users', sa.Column('profile_photo_url', sa.String(500), nullable=True))


def downgrade():
    # Remove profile_photo_url column from users table
    op.drop_column('users', 'profile_photo_url')

