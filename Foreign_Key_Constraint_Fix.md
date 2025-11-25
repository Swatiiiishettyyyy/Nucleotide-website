# Foreign Key Constraint Fix - Allow Deletion of Addresses, Members, and Products

## Problem

When trying to delete addresses, members, or products that are referenced in `order_items` table, the database throws a foreign key constraint error:

```
IntegrityError: Cannot delete or update a parent row: a foreign key constraint fails
```

This happens because:
1. `order_items` has foreign keys to `addresses`, `members`, and `products`
2. The foreign keys don't allow deletion (default RESTRICT behavior)
3. Even though we use `OrderSnapshot` for data integrity, the database constraint blocks deletion

## Solution

Since we use **OrderSnapshot** to preserve order data at the time of confirmation, we can safely allow deletion of addresses, members, and products even if they're in orders.

### Changes Made

#### 1. Model Updates (`Orders_module/Order_model.py`)

**OrderItem model:**
- Made `product_id`, `member_id`, and `address_id` nullable
- Added `ondelete="SET NULL"` to foreign key constraints
- This allows deletion - when deleted, FK becomes NULL but snapshot preserves data

**Order model:**
- Made `address_id` nullable
- Added `ondelete="SET NULL"` to foreign key constraint

#### 2. Database Migration (`database_migrations.py`)

Added `_fix_order_foreign_keys()` function that:
- Makes columns nullable in database
- Drops existing restrictive foreign key constraints
- Creates new foreign key constraints with `ON DELETE SET NULL`
- Runs automatically on application startup

#### 3. Schema Updates (`Orders_module/Order_schema.py`)

Updated response schemas to allow NULL for:
- `OrderItemData.product_id` - Optional[int]
- `OrderItemData.member_id` - Optional[int]
- `OrderItemData.address_id` - Optional[int]
- `OrderResponse.address_id` - Optional[int]
- `AddressTrackingData.address_id` - Optional[int]

#### 4. Code Already Handles NULL

The order display code already:
- Uses OrderSnapshot data (preferred)
- Falls back to original tables with NULL checks
- Handles `if item.address`, `if item.product`, etc.

## How It Works

### Before Order Confirmation (Cart Items)
- **Cannot delete** if in cart (application-level validation)
- Error shows which products are using the member/address

### After Order Confirmation (Order Items)
- **Can delete** addresses, members, products
- Foreign keys become NULL automatically (SET NULL)
- OrderSnapshot preserves all original data
- Order display uses snapshot data (not affected by deletion)

### Example Flow

1. User creates order with address_id=11
2. OrderSnapshot saves address data: `{id: 11, city: "Bangalore", ...}`
3. OrderItem created with `address_id=11` and `snapshot_id=123`
4. User deletes address 11
5. Database: `order_items.address_id` becomes NULL (SET NULL)
6. OrderSnapshot still has: `{id: 11, city: "Bangalore", ...}`
7. When displaying order: Uses snapshot data, shows "Bangalore" correctly

## Migration Details

The migration will:
1. Check if columns are nullable → Make them nullable if not
2. Drop existing foreign key constraints
3. Create new constraints with `ON DELETE SET NULL`

**SQL Generated:**
```sql
-- Make columns nullable
ALTER TABLE order_items MODIFY COLUMN address_id INT NULL;
ALTER TABLE order_items MODIFY COLUMN member_id INT NULL;
ALTER TABLE order_items MODIFY COLUMN product_id INT NULL;
ALTER TABLE orders MODIFY COLUMN address_id INT NULL;

-- Drop old constraints
ALTER TABLE order_items DROP FOREIGN KEY `old_constraint_name`;

-- Add new constraints with SET NULL
ALTER TABLE order_items 
ADD CONSTRAINT fk_order_items_address_id 
FOREIGN KEY (address_id) 
REFERENCES addresses(id) 
ON DELETE SET NULL;
```

## Benefits

✅ **Data Integrity**: OrderSnapshot preserves order data  
✅ **Flexibility**: Users can delete addresses/members/products  
✅ **No Data Loss**: Snapshot has all original data  
✅ **Clear Errors**: Cart validation still prevents deletion if in cart  

## Testing

After restart, the migration will run automatically. You should see log messages:
- "Making order_items.address_id nullable"
- "Dropping FK constraint..."
- "Added FK constraint for address_id with ON DELETE SET NULL"

Then test:
1. Create an order
2. Try to delete the address used in that order
3. Should succeed (no error)
4. View the order - should still show address from snapshot

