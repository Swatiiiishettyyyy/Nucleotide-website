"""rename metadata column to transfer_metadata in member_transfer_logs

Revision ID: 025_rename_metadata_to_transfer_metadata
Revises: 024_add_partner_consents_table
Create Date: 2025-01-17
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "025_rename_metadata_to_transfer_metadata"
down_revision = "024_add_partner_consents_table"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'member_transfer_logs' in tables:
        # Check if metadata column exists
        columns = {col['name']: col for col in inspector.get_columns('member_transfer_logs')}
        
        if 'metadata' in columns and 'transfer_metadata' not in columns:
            # Rename metadata column to transfer_metadata
            # MySQL requires existing_type when renaming columns
            op.alter_column('member_transfer_logs', 'metadata', 
                          new_column_name='transfer_metadata',
                          existing_type=sa.JSON(),
                          existing_nullable=True)


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'member_transfer_logs' in tables:
        # Check if transfer_metadata column exists
        columns = {col['name']: col for col in inspector.get_columns('member_transfer_logs')}
        
        if 'transfer_metadata' in columns and 'metadata' not in columns:
            # Rename transfer_metadata column back to metadata
            # MySQL requires existing_type when renaming columns
            op.alter_column('member_transfer_logs', 'transfer_metadata', 
                          new_column_name='metadata',
                          existing_type=sa.JSON(),
                          existing_nullable=True)

