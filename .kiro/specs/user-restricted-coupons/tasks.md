# Implementation Plan: User-Restricted Coupons

## Overview

Implement an optional per-coupon user allowlist. Coupons with allowlist entries become restricted (visible/applicable only to listed users); coupons without entries remain unrestricted and behave exactly as today.

## Tasks

- [x] 1. Add `CouponAllowedUser` model and update `Coupon` relationship
  - [x] 1.1 Add `CouponAllowedUser` SQLAlchemy model to `Cart_module/Coupon_model.py`
    - Define `coupon_allowed_users` table with columns `id`, `coupon_id` (FK → `coupons.id` ON DELETE CASCADE), `user_id` (nullable int, indexed), `mobile` (nullable VARCHAR(100), indexed)
    - Add `UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user_id")`, `UniqueConstraint("coupon_id", "mobile", name="uq_coupon_mobile")`, and `CheckConstraint("user_id IS NOT NULL OR mobile IS NOT NULL", name="ck_coupon_allowed_users_not_both_null")`
    - Add `coupon` relationship back to `Coupon`
    - Add `allowed_users = relationship("CouponAllowedUser", back_populates="coupon", cascade="all, delete-orphan")` to the existing `Coupon` model
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.2 Write property test for allowlist row validity (Property 1)
    - **Property 1: Allowlist row validity** — inserting a row with both `user_id=None` and `mobile=None` must raise `IntegrityError`
    - **Validates: Requirements 1.2**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [ ]* 1.3 Write property test for cascade delete (Property 2)
    - **Property 2: Cascade delete** — deleting a coupon must result in zero remaining `coupon_allowed_users` rows for that coupon id
    - **Validates: Requirements 1.5**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

- [x] 2. Create Alembic migration `031_add_coupon_allowed_users`
  - Create `alembic/versions/031_add_coupon_allowed_users.py` chained from `030_fix_payment_status_enum_case`
  - `upgrade()`: create `coupon_allowed_users` table with FK, indexes, unique constraints, and check constraint
  - `downgrade()`: drop the table
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 3. Add `is_user_allowed_for_coupon()` helper to `Cart_module/coupon_service.py`
  - Implement the helper: query row count for the coupon; if 0 return `True` (unrestricted); otherwise query for a matching `user_id` or `mobile` row and return whether a match exists
  - Import `CouponAllowedUser` inside the function to avoid circular imports
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

- [x] 4. Add allowlist guard to `validate_and_calculate_discount()` in `coupon_service.py`
  - After the coupon is fetched (and before the status check), look up the user's mobile from `Login_module.User.user_model.User` and call `is_user_allowed_for_coupon()`
  - If not allowed, return `(None, 0.0, "Invalid coupon code.")` — generic message to avoid leaking coupon existence
  - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 4.1 Write property test for allowlist check gates coupon application (Property 5)
    - **Property 5: Allowlist check gates coupon application** — restricted coupon + non-allowed user → validate returns `(None, 0.0, <non-empty string>)`; allowed user → validate proceeds past the allowlist check
    - **Validates: Requirements 3.1, 3.2**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [ ]* 4.2 Write property test for unrestricted coupon validation unchanged (Property 6)
    - **Property 6: Unrestricted coupon validation is unchanged** — coupon with zero allowlist entries produces identical validate result before and after the guard
    - **Validates: Requirements 3.3, 7.2**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

- [x] 5. Add allowlist filter to `list_coupons()` in `Cart_module/Cart_router.py`
  - Import `is_user_allowed_for_coupon` from `coupon_service`
  - Inside the per-coupon loop, after the per-user usage check, add: `if not is_user_allowed_for_coupon(db, coupon, current_user.id, current_user.mobile): continue`
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 5.1 Write property test for restricted coupon visibility (Property 3)
    - **Property 3: Restricted coupon visibility is allowlist-gated** — non-allowed user must not see the coupon in list; allowed user must see it
    - **Validates: Requirements 2.1, 2.3, 2.4**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [ ]* 5.2 Write property test for unrestricted coupon always visible (Property 4)
    - **Property 4: Unrestricted coupons are always visible** — coupon with zero allowlist entries appears for any authenticated user
    - **Validates: Requirements 2.2, 7.1**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

- [ ] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Add Pydantic schemas to `Cart_module/Cart_schema.py`
  - Add `AllowlistEntry` with `user_id: Optional[int]` and `mobile: Optional[str]`, plus a `@validator` that raises if both are None
  - Add `AllowlistAddRequest(coupon_code: str, entries: List[AllowlistEntry])`
  - Add `AllowlistRemoveRequest(coupon_code: str, entries: List[AllowlistEntry])`
  - Add `AllowlistEntryResponse(id: int, coupon_id: int, user_id: Optional[int], mobile: Optional[str])` with `orm_mode = True`
  - _Requirements: 4.1, 4.5, 5.1_

- [ ] 8. Add admin allowlist endpoints to `Cart_module/Cart_router.py`
  - [x] 8.1 Implement `POST /admin/coupons/allowlist/add`
    - Look up coupon by code; return 404 if not found
    - For each entry, attempt insert; skip on `IntegrityError` (duplicate); count newly added rows
    - Return `{"added": <count>, "entries": [AllowlistEntryResponse, ...]}`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 8.2 Write property test for add allowlist entries round-trip (Property 7)
    - **Property 7: Add allowlist entries round-trip** — add entries then view; all added entries must appear in the response
    - **Validates: Requirements 4.2, 6.1**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [ ]* 8.3 Write property test for add is idempotent (Property 8)
    - **Property 8: Add is idempotent** — adding the same entry twice must not create a duplicate row and must report 0 newly added for the duplicate
    - **Validates: Requirements 4.4**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [ ]* 8.4 Write property test for non-existent coupon returns 404 (Property 9)
    - **Property 9: Non-existent coupon returns 404** — all three admin endpoints must return HTTP 404 for a coupon code not in the DB
    - **Validates: Requirements 4.3, 5.4, 6.2**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [x] 8.5 Implement `DELETE /admin/coupons/allowlist/remove`
    - Look up coupon by code; return 404 if not found
    - For each entry, delete matching row(s) by `user_id` or `mobile`; skip silently if not found
    - Return `{"removed": <count>}`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 8.6 Write property test for remove allowlist entries round-trip (Property 10)
    - **Property 10: Remove allowlist entries round-trip** — add all entries, remove all, view; result must be empty list
    - **Validates: Requirements 5.2, 6.3**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [ ]* 8.7 Write property test for remove is no-op for absent entries (Property 11)
    - **Property 11: Remove is a no-op for absent entries** — removing an entry not in the allowlist must not error and must report 0 removed
    - **Validates: Requirements 5.3**
    - Place in `Cart_module/tests/test_coupon_allowlist.py`

  - [x] 8.8 Implement `GET /admin/coupons/allowlist`
    - Accept `coupon_code` as a query parameter; return 404 if not found
    - Return all `CouponAllowedUser` rows for that coupon as `List[AllowlistEntryResponse]` (empty list for unrestricted coupons)
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 9. Create test file `Cart_module/tests/test_coupon_allowlist.py`
  - Set up the test module with Hypothesis `@settings(max_examples=100)` and an in-memory SQLite session fixture
  - Wire all property-based tests (Properties 1–11) using `hypothesis.strategies` for random coupon/user/entry generation
  - Include unit test cases: schema unchanged, 404 on missing coupon, 422 on missing user_id+mobile, empty list when only coupon is restricted and user not on allowlist
  - _Requirements: 1.1–1.5, 2.1–2.4, 3.1–3.3, 4.1–4.5, 5.1–5.4, 6.1–6.3, 7.1–7.3_

- [ ] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)`
- The allowlist check returns the generic "Invalid coupon code." message to prevent coupon-existence probing
- No changes are made to the `coupons` table schema — the feature is purely additive
