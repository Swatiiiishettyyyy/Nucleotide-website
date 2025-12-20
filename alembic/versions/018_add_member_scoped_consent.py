"""add member scoped consent

Revision ID: 018_add_member_scoped_consent
Revises: 017_add_soft_delete_flags
Create Date: 2025-12-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "018_add_member_scoped_consent"
down_revision = "017_add_soft_delete_flags"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if member_id column already exists in user_consents
    user_consents_columns = {col['name']: col for col in inspector.get_columns('user_consents')}
    
    # Add member_id column to user_consents table (if it doesn't exist)
    if 'member_id' not in user_consents_columns:
        op.add_column(
            "user_consents",
            sa.Column("member_id", sa.Integer(), nullable=True, index=True)
        )
    
    # Drop old unique index (if it exists)
    indexes = [idx['name'] for idx in inspector.get_indexes('user_consents')]
    if 'idx_user_phone_product' in indexes:
        try:
            op.drop_index("idx_user_phone_product", table_name="user_consents")
        except Exception:
            pass
    
    # Check if foreign key already exists - we'll need to drop it temporarily to alter column
    fk_constraints = [fk['name'] for fk in inspector.get_foreign_keys('user_consents')]
    fk_exists = 'fk_user_consents_member' in fk_constraints
    
    # Drop foreign key if it exists (we'll recreate it after altering column)
    if fk_exists:
        op.drop_constraint("fk_user_consents_member", "user_consents", type_="foreignkey")
    
    # Check if login_consent_shown column already exists in members
    members_columns = {col['name']: col for col in inspector.get_columns('members')}
    
    # Add login_consent_shown flag to members table (if it doesn't exist)
    if 'login_consent_shown' not in members_columns:
        op.add_column(
            "members",
            sa.Column(
                "login_consent_shown",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
                index=True
            )
        )
    
    # Migrate existing data: For each user_consent, try to assign to first member of that user
    # This is a best-effort migration - existing consents will be assigned to first member
    connection = op.get_bind()
    
    # First, clean up any invalid member_id values (pointing to non-existent or deleted members)
    connection.execute(sa.text("""
        UPDATE user_consents uc
        LEFT JOIN members m ON uc.member_id = m.id AND m.is_deleted = 0
        SET uc.member_id = NULL
        WHERE uc.member_id IS NOT NULL AND m.id IS NULL
    """))
    
    # Get all user_consents without member_id
    result = connection.execute(sa.text("""
        SELECT DISTINCT user_id FROM user_consents WHERE member_id IS NULL
    """))
    
    user_ids = [row[0] for row in result]
    
    for user_id in user_ids:
        # Get first member for this user
        member_result = connection.execute(
            sa.text("SELECT id FROM members WHERE user_id = :user_id AND is_deleted = 0 ORDER BY created_at ASC LIMIT 1"),
            {"user_id": user_id}
        )
        member_row = member_result.fetchone()
        
        if member_row:
            member_id = member_row[0]
            # Update all consents for this user to point to first member
            connection.execute(
                sa.text("UPDATE user_consents SET member_id = :member_id WHERE user_id = :user_id AND member_id IS NULL"),
                {"member_id": member_id, "user_id": user_id}
            )
        else:
            # If no member exists for this user, delete the consent records
            # (they can't be migrated and would violate FK constraint)
            connection.execute(
                sa.text("DELETE FROM user_consents WHERE user_id = :user_id AND member_id IS NULL"),
                {"user_id": user_id}
            )
    
    # Final cleanup: Delete any remaining rows with NULL member_id
    # (these are orphaned records that couldn't be assigned to any member)
    connection.execute(sa.text("DELETE FROM user_consents WHERE member_id IS NULL"))
    
    # Verify all member_id values are valid before proceeding
    invalid_count = connection.execute(sa.text("""
        SELECT COUNT(*) FROM user_consents uc
        LEFT JOIN members m ON uc.member_id = m.id AND m.is_deleted = 0
        WHERE uc.member_id IS NOT NULL AND m.id IS NULL
    """)).scalar()
    
    if invalid_count > 0:
        # If there are still invalid references, delete them
        connection.execute(sa.text("""
            DELETE uc FROM user_consents uc
            LEFT JOIN members m ON uc.member_id = m.id AND m.is_deleted = 0
            WHERE uc.member_id IS NOT NULL AND m.id IS NULL
        """))
    
    # Make member_id NOT NULL after migration (if it's still nullable)
    # Refresh inspector to get updated column state
    inspector = sa.inspect(connection)
    user_consents_columns_updated = {col['name']: col for col in inspector.get_columns('user_consents')}
    
    # MySQL requires existing_type when altering columns
    # Only make NOT NULL if column exists and is currently nullable
    if 'member_id' in user_consents_columns_updated:
        member_id_col = user_consents_columns_updated['member_id']
        if member_id_col.get('nullable', True):
            # Check if there are any rows - if table is empty, we can still make it NOT NULL
            # But if there are rows, ensure none are NULL
            row_count = connection.execute(sa.text("SELECT COUNT(*) FROM user_consents")).scalar()
            if row_count == 0 or connection.execute(sa.text("SELECT COUNT(*) FROM user_consents WHERE member_id IS NULL")).scalar() == 0:
                op.alter_column(
                    "user_consents",
                    "member_id",
                    existing_type=sa.Integer(),
                    nullable=False
                )
    
    # Recreate foreign key constraint (if it was dropped or needs to be created)
    inspector = sa.inspect(connection)
    fk_constraints_after = [fk['name'] for fk in inspector.get_foreign_keys('user_consents')]
    if 'fk_user_consents_member' not in fk_constraints_after:
        op.create_foreign_key(
            "fk_user_consents_member",
            "user_consents",
            "members",
            ["member_id"],
            ["id"],
            ondelete="CASCADE"
        )
    
    # Create new unique index with member_id (if it doesn't exist)
    indexes_after = [idx['name'] for idx in inspector.get_indexes('user_consents')]
    if 'idx_member_product' not in indexes_after:
        op.create_index(
            "idx_member_product",
            "user_consents",
            ["member_id", "product_id"],
            unique=True
        )


def downgrade():
    # Remove login_consent_shown from members
    op.drop_column("members", "login_consent_shown")
    
    # Drop new index
    try:
        op.drop_index("idx_member_product", table_name="user_consents")
    except Exception:
        pass
    
    # Recreate old index
    op.create_index(
        "idx_user_phone_product",
        "user_consents",
        ["user_phone", "product_id"],
        unique=True
    )
    
    # Drop foreign key
    try:
        op.drop_constraint("fk_user_consents_member", "user_consents", type_="foreignkey")
    except Exception:
        pass
    
    # Remove member_id column
    op.drop_column("user_consents", "member_id")

