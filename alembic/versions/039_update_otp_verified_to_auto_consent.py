"""update OTP_VERIFIED records to auto consent

Revision ID: 039_update_otp_verified_to_auto_consent
Revises: 038_add_partner_consent_otp_fields
Create Date: 2025-01-17

Updates existing partner consent records with OTP_VERIFIED status to CONSENT_GIVEN.
Since OTP verification now automatically grants consent, any records stuck in OTP_VERIFIED
status should be updated to CONSENT_GIVEN with partner_consent = "yes" and final_status = "yes"
(if user_consent is also "yes").
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "039_update_otp_verified_to_auto_consent"
down_revision = "038_add_partner_consent_otp_fields"  # or use the revision ID if different
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Update existing records with OTP_VERIFIED status to CONSENT_GIVEN.
    OTP verification now automatically grants consent, so these records should be updated.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'partner_consents' in tables:
        try:
            # First, count how many records need updating
            count_result = connection.execute(text("""
                SELECT COUNT(*) as count 
                FROM partner_consents 
                WHERE request_status = 'OTP_VERIFIED'
            """))
            count = count_result.fetchone()[0] if count_result else 0
            
            if count > 0:
                # Update records with OTP_VERIFIED status
                # If user_consent is "yes", set partner_consent to "yes" and final_status to "yes"
                # If user_consent is not "yes", leave as is (shouldn't happen, but handle gracefully)
                op.execute(text("""
                    UPDATE partner_consents 
                    SET request_status = 'CONSENT_GIVEN',
                        partner_consent = CASE 
                            WHEN user_consent = 'yes' THEN 'yes'
                            ELSE partner_consent
                        END,
                        final_status = CASE 
                            WHEN user_consent = 'yes' THEN 'yes'
                            ELSE final_status
                        END
                    WHERE request_status = 'OTP_VERIFIED'
                """))
                print(f"Updated {count} partner consent record(s) from OTP_VERIFIED to CONSENT_GIVEN")
            else:
                print("No records with OTP_VERIFIED status found. Migration completed successfully.")
            
        except Exception as e:
            # If update fails, log warning but continue
            print(f"Warning: Could not update OTP_VERIFIED records: {e}")


def downgrade() -> None:
    """
    Downgrade: Revert OTP_VERIFIED records back (not really possible to know which ones were auto-updated,
    so we'll just leave them as CONSENT_GIVEN since that's the correct state anyway).
    """
    # No downgrade needed - CONSENT_GIVEN is the correct state for records that had OTP verified
    # Even if we revert the code change, these records should remain as CONSENT_GIVEN
    pass

