"""add partner consent OTP flow fields

Revision ID: 038_add_partner_consent_otp_fields
Revises: d30672f6c4e3
Create Date: 2025-01-17

Adds OTP-based partner consent flow fields to partner_consents table:
- Request state machine fields (request_status, request_id)
- OTP tracking fields (otp_expires_at, otp_sent_at)
- Request expiration fields (request_expires_at, last_request_created_at)
- Rate limiting fields (failed_attempts, resend_count, total_attempts)
- Revocation tracking (revoked_at)
- Updates default values for partner_consent and consent_source
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "038_add_partner_consent_otp_fields"
down_revision = "d30672f6c4e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'partner_consents' in tables:
        # Add request state machine fields
        op.add_column('partner_consents', 
            sa.Column('request_status', sa.String(20), nullable=False, server_default='PENDING_REQUEST'))
        op.add_column('partner_consents', 
            sa.Column('request_id', sa.String(50), nullable=True))
        
        # Add OTP tracking fields
        op.add_column('partner_consents', 
            sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('partner_consents', 
            sa.Column('otp_sent_at', sa.DateTime(timezone=True), nullable=True))
        
        # Add request expiration fields
        op.add_column('partner_consents', 
            sa.Column('request_expires_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('partner_consents', 
            sa.Column('last_request_created_at', sa.DateTime(timezone=True), nullable=True))
        
        # Add rate limiting fields
        op.add_column('partner_consents', 
            sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'))
        op.add_column('partner_consents', 
            sa.Column('resend_count', sa.Integer(), nullable=False, server_default='0'))
        op.add_column('partner_consents', 
            sa.Column('total_attempts', sa.Integer(), nullable=False, server_default='1'))
        
        # Add revocation tracking
        op.add_column('partner_consents', 
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
        
        # Create indexes
        op.create_index('ix_partner_consents_request_status', 'partner_consents', ['request_status'], unique=False)
        op.create_index('ix_partner_consents_request_id', 'partner_consents', ['request_id'], unique=True)
        
        # Update existing records to have proper defaults
        # Set request_status for existing records based on their current state
        try:
            op.execute(text("""
                UPDATE partner_consents 
                SET request_status = CASE 
                    WHEN final_status = 'yes' THEN 'CONSENT_GIVEN'
                    WHEN partner_consent = 'no' THEN 'DECLINED'
                    ELSE 'PENDING_REQUEST'
                END
            """))
        except Exception as e:
            # If update fails, continue - new records will have correct defaults
            print(f"Warning: Could not update existing request_status: {e}")
        
        # Alter column defaults for partner_consent and consent_source
        # Note: This changes the default for new records, existing records keep their values
        try:
            # For MySQL, we need to alter the column to change the default
            dialect_name = connection.dialect.name
            if dialect_name == 'mysql':
                op.execute(text("ALTER TABLE partner_consents MODIFY COLUMN partner_consent VARCHAR(10) NOT NULL DEFAULT 'pending'"))
                op.execute(text("ALTER TABLE partner_consents MODIFY COLUMN consent_source VARCHAR(20) NOT NULL DEFAULT 'partner_otp'"))
            else:
                # For other databases (PostgreSQL, SQLite)
                op.alter_column('partner_consents', 'partner_consent', server_default='pending')
                op.alter_column('partner_consents', 'consent_source', server_default='partner_otp')
        except Exception as e:
            # If altering defaults fails, continue - model defaults will handle it
            print(f"Warning: Could not update column defaults: {e}")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'partner_consents' in tables:
        # Drop indexes first
        try:
            op.drop_index('ix_partner_consents_request_id', table_name='partner_consents')
            op.drop_index('ix_partner_consents_request_status', table_name='partner_consents')
        except Exception:
            pass
        
        # Drop columns
        try:
            op.drop_column('partner_consents', 'revoked_at')
            op.drop_column('partner_consents', 'total_attempts')
            op.drop_column('partner_consents', 'resend_count')
            op.drop_column('partner_consents', 'failed_attempts')
            op.drop_column('partner_consents', 'last_request_created_at')
            op.drop_column('partner_consents', 'request_expires_at')
            op.drop_column('partner_consents', 'otp_sent_at')
            op.drop_column('partner_consents', 'otp_expires_at')
            op.drop_column('partner_consents', 'request_id')
            op.drop_column('partner_consents', 'request_status')
        except Exception:
            pass

