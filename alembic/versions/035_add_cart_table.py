"""Add cart table and update cart_items foreign key

Revision ID: 035_add_cart_table
Revises: 034_add_placed_by_member_id
Create Date: 2025-01-27

Tags: cart, cart_items
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "035_add_cart_table"
down_revision = "034_add_placed_by_member_id"
branch_labels = None
depends_on = None


def upgrade():
    """
    Create cart table and update cart_items to reference it.
    Migrates existing cart_items to use proper cart table.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Step 1: Create carts table
    if 'carts' not in inspector.get_table_names():
        op.create_table(
            'carts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
        )
        op.create_index(op.f('ix_carts_id'), 'carts', ['id'], unique=False)
        op.create_index(op.f('ix_carts_user_id'), 'carts', ['user_id'], unique=False)
        op.create_index(op.f('ix_carts_is_active'), 'carts', ['is_active'], unique=False)
        print("  - Created carts table")
    
    # Step 2: Migrate existing cart_items to use cart table
        # For each user with cart items, create a cart and update cart_items
        if 'cart_items' in inspector.get_table_names():
            cart_items_columns = {col['name'] for col in inspector.get_columns('cart_items')}
            
            # Get all unique user_ids with cart items (including deleted ones for migration)
            result = connection.execute(sa.text("""
                SELECT DISTINCT user_id 
                FROM cart_items 
                GROUP BY user_id
            """))
            user_ids = [row[0] for row in result]
            
            print(f"  - Found {len(user_ids)} users with cart items")
            
            # Create cart for each user and update cart_items
            for user_id in user_ids:
                # Check if cart already exists for this user (shouldn't happen, but safety check)
                if dialect_name == 'mysql':
                    active_check = "is_active = 1"
                else:
                    active_check = "is_active = true"
                
                existing_cart = connection.execute(sa.text(f"""
                    SELECT id FROM carts 
                    WHERE user_id = :user_id AND {active_check}
                    LIMIT 1
                """), {"user_id": user_id}).fetchone()
                
                if existing_cart:
                    cart_id = existing_cart[0]
                    print(f"    - Using existing cart {cart_id} for user {user_id}")
                else:
                    # Create cart for this user
                    result = connection.execute(sa.text("""
                        INSERT INTO carts (user_id, is_active, created_at)
                        VALUES (:user_id, 1, CURRENT_TIMESTAMP)
                    """), {"user_id": user_id})
                    
                    cart_id = result.lastrowid
                    print(f"    - Created cart {cart_id} for user {user_id}")
                
                # Update all cart_items for this user to use the new cart_id
                # Update items where cart_id is NULL or doesn't match the new cart_id
                # This handles both new items and items that had old cart_id values (from item.id)
                update_result = connection.execute(sa.text("""
                    UPDATE cart_items 
                    SET cart_id = :cart_id
                    WHERE user_id = :user_id 
                    AND (cart_id IS NULL OR cart_id != :cart_id)
                """), {"cart_id": cart_id, "user_id": user_id})
                
                updated_count = update_result.rowcount
                if updated_count > 0:
                    print(f"      - Updated {updated_count} cart items for user {user_id}")
        
        # Step 3: Make cart_id NOT NULL and add foreign key constraint
        # Handle any remaining NULL cart_id values (shouldn't happen after step 2, but safety check)
        null_count = connection.execute(sa.text("""
            SELECT COUNT(*) FROM cart_items WHERE cart_id IS NULL
        """)).scalar()
        
        if null_count > 0:
            print(f"  - Found {null_count} cart items with NULL cart_id, fixing...")
            # Update any remaining NULL values
            # Use database-agnostic boolean check
            if dialect_name == 'mysql':
                active_condition = "carts.is_active = 1"
            else:
                active_condition = "carts.is_active = true"
            
            connection.execute(sa.text(f"""
                UPDATE cart_items 
                SET cart_id = (
                    SELECT id FROM carts 
                    WHERE carts.user_id = cart_items.user_id 
                    AND {active_condition}
                    LIMIT 1
                )
                WHERE cart_id IS NULL
            """))
            
            # Check if there are still NULL values (user has no cart - shouldn't happen)
            remaining_null = connection.execute(sa.text("""
                SELECT COUNT(*) FROM cart_items WHERE cart_id IS NULL
            """)).scalar()
            
            if remaining_null > 0:
                print(f"  - Warning: {remaining_null} cart items still have NULL cart_id (users with no cart)")
                # For these edge cases, we'll create carts for them
                null_user_ids = connection.execute(sa.text("""
                    SELECT DISTINCT user_id FROM cart_items WHERE cart_id IS NULL
                """)).fetchall()
                
                for (user_id,) in null_user_ids:
                    result = connection.execute(sa.text("""
                        INSERT INTO carts (user_id, is_active, created_at)
                        VALUES (:user_id, 1, CURRENT_TIMESTAMP)
                    """), {"user_id": user_id})
                    cart_id = result.lastrowid
                    
                    connection.execute(sa.text("""
                        UPDATE cart_items 
                        SET cart_id = :cart_id
                        WHERE user_id = :user_id AND cart_id IS NULL
                    """), {"cart_id": cart_id, "user_id": user_id})
                    print(f"    - Created cart {cart_id} for user {user_id} (had NULL cart_id items)")
        
        # Now make cart_id NOT NULL
        if dialect_name == 'mysql':
            # MySQL specific: modify column to be NOT NULL
            connection.execute(sa.text("""
                ALTER TABLE cart_items 
                MODIFY COLUMN cart_id INTEGER NOT NULL
            """))
        else:
            # SQLite/PostgreSQL
            connection.execute(sa.text("""
                ALTER TABLE cart_items 
                ALTER COLUMN cart_id SET NOT NULL
            """))
        
        print("  - Made cart_id NOT NULL in cart_items")
        
        # Add foreign key constraint
        try:
            op.create_foreign_key(
                'fk_cart_items_cart_id',
                'cart_items', 'carts',
                ['cart_id'], ['id'],
                ondelete='CASCADE'
            )
            print("  - Added foreign key constraint: cart_items.cart_id -> carts.id")
        except Exception as e:
            print(f"  - Warning: Could not add foreign key constraint: {e}")
            print("    (This may already exist or database doesn't support it)")
    
    # Step 4: Add unique constraint for one active cart per user
    try:
        # For MySQL, we'll use a unique index on (user_id, is_active) with a check
        # Note: MySQL doesn't support partial unique indexes directly, so we'll create a regular unique index
        # and rely on application logic to ensure only one active cart per user
        if dialect_name == 'mysql':
            # Create unique index on user_id and is_active
            # Application logic ensures only one is_active=True per user
            op.create_index(
                'uq_user_active_cart',
                'carts',
                ['user_id', 'is_active'],
                unique=False  # Not unique because multiple inactive carts are allowed
            )
            print("  - Added index for active cart lookup (MySQL)")
        else:
            # For PostgreSQL/SQLite, try to create partial unique index
            try:
                connection.execute(sa.text("""
                    CREATE UNIQUE INDEX uq_user_active_cart 
                    ON carts (user_id) 
                    WHERE is_active = true
                """))
                print("  - Added partial unique index: one active cart per user")
            except Exception:
                # Fallback: regular unique index (application logic handles the constraint)
                op.create_index(
                    'uq_user_active_cart',
                    'carts',
                    ['user_id', 'is_active'],
                    unique=False
                )
                print("  - Added index for active cart lookup (fallback)")
    except Exception as e:
        print(f"  - Warning: Could not add unique constraint: {e}")
        print("    (Application logic ensures only one active cart per user)")


def downgrade():
    """
    Remove cart table and revert cart_items to nullable cart_id.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    dialect_name = connection.dialect.name
    
    # Step 1: Remove foreign key constraint
    if 'cart_items' in inspector.get_table_names():
        try:
            op.drop_constraint('fk_cart_items_cart_id', 'cart_items', type_='foreignkey')
            print("  - Removed foreign key constraint")
        except Exception:
            pass
        
        # Step 2: Make cart_id nullable again
        if dialect_name == 'mysql':
            connection.execute(sa.text("""
                ALTER TABLE cart_items 
                MODIFY COLUMN cart_id INTEGER NULL
            """))
        else:
            connection.execute(sa.text("""
                ALTER TABLE cart_items 
                ALTER COLUMN cart_id DROP NOT NULL
            """))
        print("  - Made cart_id nullable in cart_items")
    
    # Step 3: Drop unique constraint
    try:
        op.drop_index('uq_user_active_cart', table_name='carts')
        print("  - Removed unique constraint")
    except Exception:
        pass
    
    # Step 4: Drop carts table
    if 'carts' in inspector.get_table_names():
        op.drop_index(op.f('ix_carts_is_active'), table_name='carts')
        op.drop_index(op.f('ix_carts_user_id'), table_name='carts')
        op.drop_index(op.f('ix_carts_id'), table_name='carts')
        op.drop_table('carts')
        print("  - Dropped carts table")

