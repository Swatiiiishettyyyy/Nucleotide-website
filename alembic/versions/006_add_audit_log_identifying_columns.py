"""Add identifying columns to audit log tables

Revision ID: 006_audit_identifiers
Revises: 005_order_fks
Create Date: 2024-01-06 00:00:00.000000

Tags: audit, logging, identifiers
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_audit_identifiers'
down_revision: Union[str, None] = '005_order_fks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add identifying columns to audit log tables for clear member/address identification.
    - member_audit_logs: member_name, member_identifier
    - address_audit: address_label, address_identifier
    Also make address_audit.address_id nullable for deletion logs.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Update member_audit_logs
    if 'member_audit_logs' in inspector.get_table_names():
        member_audit_columns = {col['name'] for col in inspector.get_columns('member_audit_logs')}
        
        if 'member_name' not in member_audit_columns:
            op.add_column('member_audit_logs', sa.Column('member_name', sa.String(length=255), nullable=True))
            op.create_index(op.f('ix_member_audit_logs_member_name'), 'member_audit_logs', ['member_name'], unique=False)
        
        if 'member_identifier' not in member_audit_columns:
            op.add_column('member_audit_logs', sa.Column('member_identifier', sa.String(length=100), nullable=True))
    
    # Update address_audit
    if 'address_audit' in inspector.get_table_names():
        address_audit_columns = {col['name'] for col in inspector.get_columns('address_audit')}
        
        if 'address_label' not in address_audit_columns:
            op.add_column('address_audit', sa.Column('address_label', sa.String(length=255), nullable=True))
            op.create_index(op.f('ix_address_audit_address_label'), 'address_audit', ['address_label'], unique=False)
        
        if 'address_identifier' not in address_audit_columns:
            op.add_column('address_audit', sa.Column('address_identifier', sa.String(length=200), nullable=True))
        
        # Make address_id nullable for deletion logs
        address_audit_columns_updated = {col['name']: col for col in inspector.get_columns('address_audit')}
        if 'address_id' in address_audit_columns_updated and not address_audit_columns_updated['address_id'].get('nullable', False):
            op.alter_column('address_audit', 'address_id', nullable=True)


def downgrade() -> None:
    """Remove identifying columns from audit log tables"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'member_audit_logs' in inspector.get_table_names():
        op.drop_index(op.f('ix_member_audit_logs_member_name'), table_name='member_audit_logs')
        op.drop_column('member_audit_logs', 'member_identifier')
        op.drop_column('member_audit_logs', 'member_name')
    
    if 'address_audit' in inspector.get_table_names():
        op.drop_index(op.f('ix_address_audit_address_label'), table_name='address_audit')
        op.drop_column('address_audit', 'address_identifier')
        op.drop_column('address_audit', 'address_label')
        # Note: Not reverting address_id nullable change as it may break existing deletion logs

