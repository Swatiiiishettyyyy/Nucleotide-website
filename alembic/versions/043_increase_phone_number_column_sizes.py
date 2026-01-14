"""increase_phone_number_column_sizes

Revision ID: 043_increase_phone_number_column_sizes
Revises: 042_make_location_tracking_optional
Create Date: 2025-01-XX 00:00:00.000000

Tags: encryption, phone_numbers, schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '043_increase_phone_number_column_sizes'
down_revision: Union[str, None] = '042_make_location_tracking_optional'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Increase phone number column sizes to accommodate encrypted values.
    Encrypted phone numbers are ~52-60 characters long, so we increase to 100 for safety.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # List of tables and columns to update
    columns_to_update = [
        ('users', 'mobile'),
        ('members', 'mobile'),
        ('user_consents', 'user_phone'),
        ('partner_consents', 'user_mobile'),
        ('partner_consents', 'partner_mobile'),
        ('phone_change_requests', 'old_phone'),
        ('phone_change_requests', 'new_phone'),
    ]
    
    for table_name, column_name in columns_to_update:
        # Check if table exists
        if table_name not in inspector.get_table_names():
            print(f"Skipping {table_name}.{column_name} - table does not exist")
            continue
        
        # Check if column exists
        columns = {col['name']: col for col in inspector.get_columns(table_name)}
        if column_name not in columns:
            print(f"Skipping {table_name}.{column_name} - column does not exist")
            continue
        
        # Get current column info
        current_col = columns[column_name]
        current_length = current_col.get('type', {}).length if hasattr(current_col.get('type'), 'length') else None
        
        # Skip if already larger than 100
        if current_length and current_length >= 100:
            print(f"Skipping {table_name}.{column_name} - already size {current_length}")
            continue
        
        # Alter column to increase size
        print(f"Updating {table_name}.{column_name} from {current_length} to 100")
        
        if dialect_name == 'mysql':
            # MySQL syntax
            op.execute(text(f"ALTER TABLE `{table_name}` MODIFY COLUMN `{column_name}` VARCHAR(100)"))
        elif dialect_name == 'postgresql':
            # PostgreSQL syntax
            op.execute(text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE VARCHAR(100)'))
        elif dialect_name == 'sqlite':
            # SQLite doesn't support ALTER COLUMN easily - would need to recreate table
            # For now, just log a warning
            print(f"WARNING: SQLite detected. Column {table_name}.{column_name} size cannot be changed easily.")
            print(f"         You may need to manually recreate the table or use a migration tool.")
        else:
            # Generic SQLAlchemy approach
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.String(current_length or 20),
                type_=sa.String(100),
                existing_nullable=current_col.get('nullable', True),
            )


def downgrade() -> None:
    """
    Revert phone number column sizes back to 20.
    WARNING: This will fail if any encrypted phone numbers are longer than 20 characters!
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # List of tables and columns to revert
    columns_to_update = [
        ('users', 'mobile'),
        ('members', 'mobile'),
        ('user_consents', 'user_phone'),
        ('partner_consents', 'user_mobile'),
        ('partner_consents', 'partner_mobile'),
        ('phone_change_requests', 'old_phone'),
        ('phone_change_requests', 'new_phone'),
    ]
    
    for table_name, column_name in columns_to_update:
        # Check if table exists
        if table_name not in inspector.get_table_names():
            continue
        
        # Check if column exists
        columns = {col['name']: col for col in inspector.get_columns(table_name)}
        if column_name not in columns:
            continue
        
        # Get current column info
        current_col = columns[column_name]
        
        # Alter column to decrease size (WARNING: May fail if data is too long)
        print(f"Reverting {table_name}.{column_name} to 20 (WARNING: May fail if encrypted data exists)")
        
        if dialect_name == 'mysql':
            op.execute(text(f"ALTER TABLE `{table_name}` MODIFY COLUMN `{column_name}` VARCHAR(20)"))
        elif dialect_name == 'postgresql':
            op.execute(text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE VARCHAR(20)'))
        elif dialect_name == 'sqlite':
            print(f"WARNING: SQLite detected. Column {table_name}.{column_name} cannot be reverted easily.")
        else:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.String(100),
                type_=sa.String(20),
                existing_nullable=current_col.get('nullable', True),
            )

