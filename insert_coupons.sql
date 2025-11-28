-- SQL Script to Insert 5 Coupons into Database
-- Table: coupons

-- ============================================
-- Coupon 1: 10% Off (Percentage Discount)
-- ============================================
INSERT INTO coupons (
    coupon_code,
    description,
    discount_type,
    discount_value,
    min_order_amount,
    max_discount_amount,
    max_uses,
    valid_from,
    valid_until,
    status,
    created_at
) VALUES (
    'SAVE10',
    'Get 10% off on your order. Maximum discount ₹500.',
    'percentage',
    10.0,
    500.0,
    500.0,
    100,
    '2024-01-01 00:00:00',
    '2025-12-31 23:59:59',
    'active',
    NOW()
);

-- ============================================
-- Coupon 2: ₹200 Fixed Discount
-- ============================================
INSERT INTO coupons (
    coupon_code,
    description,
    discount_type,
    discount_value,
    min_order_amount,
    max_discount_amount,
    max_uses,
    valid_from,
    valid_until,
    status,
    created_at
) VALUES (
    'FLAT200',
    'Get flat ₹200 off on orders above ₹1000',
    'fixed',
    200.0,
    1000.0,
    NULL,
    50,
    '2024-01-01 00:00:00',
    '2025-12-31 23:59:59',
    'active',
    NOW()
);

-- ============================================
-- Coupon 3: 25% Off Sale Coupon
-- ============================================
INSERT INTO coupons (
    coupon_code,
    description,
    discount_type,
    discount_value,
    min_order_amount,
    max_discount_amount,
    max_uses,
    valid_from,
    valid_until,
    status,
    created_at
) VALUES (
    'SALE25',
    'Big Sale - 25% off on all orders above ₹2000',
    'percentage',
    25.0,
    2000.0,
    2000.0,
    NULL,
    '2024-01-01 00:00:00',
    '2025-12-31 23:59:59',
    'active',
    NOW()
);

-- ============================================
-- Coupon 4: Free Shipping (₹50 Off)
-- ============================================
INSERT INTO coupons (
    coupon_code,
    description,
    discount_type,
    discount_value,
    min_order_amount,
    max_discount_amount,
    max_uses,
    valid_from,
    valid_until,
    status,
    created_at
) VALUES (
    'FREESHIP',
    'Free shipping on all orders',
    'fixed',
    50.0,
    0.0,
    NULL,
    NULL,
    '2024-01-01 00:00:00',
    '2025-12-31 23:59:59',
    'active',
    NOW()
);

-- ============================================
-- Coupon 5: Welcome Bonus (50% Off)
-- ============================================
INSERT INTO coupons (
    coupon_code,
    description,
    discount_type,
    discount_value,
    min_order_amount,
    max_discount_amount,
    max_uses,
    valid_from,
    valid_until,
    status,
    created_at
) VALUES (
    'WELCOME50',
    'Welcome bonus - 50% off for new users',
    'percentage',
    50.0,
    0.0,
    1000.0,
    1,
    '2024-01-01 00:00:00',
    '2025-12-31 23:59:59',
    'active',
    NOW()
);

