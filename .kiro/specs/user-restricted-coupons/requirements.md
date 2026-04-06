# Requirements Document

## Introduction

This feature adds user-level visibility and applicability restrictions to coupons on the Nucleotide website. Currently, all active coupons are shown to every authenticated user via `/list-coupons` and can be applied by any user. The new feature allows administrators to optionally restrict specific coupons so they are only visible and applicable to a defined allowlist of users, identified by user ID or phone number (mobile). Coupons without a restriction remain universally available as before.

## Glossary

- **Coupon**: A discount code stored in the `coupons` table with fields such as `coupon_code`, `discount_type`, `discount_value`, `status`, and validity dates.
- **Restricted_Coupon**: A Coupon that has one or more entries in the `coupon_allowed_users` table, limiting visibility and applicability to those users only.
- **Unrestricted_Coupon**: A Coupon with no entries in the `coupon_allowed_users` table; visible and applicable to all authenticated users.
- **Allowlist**: The set of user IDs and/or phone numbers associated with a Restricted_Coupon via the `coupon_allowed_users` table.
- **Coupon_Service**: The module `Cart_module/coupon_service.py` responsible for coupon validation and discount calculation.
- **List_Coupons_Endpoint**: The `GET /list-coupons` route in `Cart_module/Cart_router.py`.
- **Admin_Endpoint**: A privileged API endpoint for managing coupon allowlists, not requiring end-user authentication.
- **User**: An authenticated entity identified by `user_id` (integer) and `mobile` (phone number string) from `Login_module/User/user_model.py`.
- **CouponAllowedUser**: A join-table record linking a Coupon to a specific User via `user_id` or `mobile`.

---

## Requirements

### Requirement 1: Coupon Allowlist Data Model

**User Story:** As an administrator, I want to associate specific users with a coupon, so that I can restrict which users can see and use that coupon.

#### Acceptance Criteria

1. THE System SHALL provide a `coupon_allowed_users` table with columns: `id`, `coupon_id` (FK to `coupons.id`), `user_id` (nullable integer), and `mobile` (nullable string).
2. THE System SHALL enforce that each `coupon_allowed_users` row has at least one of `user_id` or `mobile` populated (not both null).
3. THE System SHALL enforce a unique constraint on `(coupon_id, user_id)` where `user_id` is not null.
4. THE System SHALL enforce a unique constraint on `(coupon_id, mobile)` where `mobile` is not null.
5. WHEN a Coupon is deleted, THE System SHALL cascade-delete all associated `coupon_allowed_users` rows.

---

### Requirement 2: Restricted Coupon Visibility in List Coupons

**User Story:** As a user, I want the coupon list to only show me coupons I am eligible for, so that I don't see offers that I cannot use.

#### Acceptance Criteria

1. WHEN the List_Coupons_Endpoint is called by an authenticated User, THE List_Coupons_Endpoint SHALL exclude any Restricted_Coupon for which the User's `user_id` does not appear in the Allowlist AND the User's `mobile` does not appear in the Allowlist.
2. WHEN the List_Coupons_Endpoint is called by an authenticated User, THE List_Coupons_Endpoint SHALL include all Unrestricted_Coupons that pass the existing active/validity/usage-limit checks.
3. WHEN the List_Coupons_Endpoint is called by an authenticated User, THE List_Coupons_Endpoint SHALL include a Restricted_Coupon if the User's `user_id` matches any Allowlist entry for that coupon.
4. WHEN the List_Coupons_Endpoint is called by an authenticated User, THE List_Coupons_Endpoint SHALL include a Restricted_Coupon if the User's `mobile` matches any Allowlist entry for that coupon.

---

### Requirement 3: Restricted Coupon Validation on Apply

**User Story:** As a user, I want coupon application to be rejected if I am not on the allowlist, so that restricted coupons cannot be applied by unauthorized users.

#### Acceptance Criteria

1. WHEN a User attempts to apply a Restricted_Coupon and the User's `user_id` is not in the Allowlist AND the User's `mobile` is not in the Allowlist, THEN THE Coupon_Service SHALL return an error message indicating the coupon is invalid.
2. WHEN a User attempts to apply a Restricted_Coupon and the User's `user_id` or `mobile` is present in the Allowlist, THE Coupon_Service SHALL proceed with all existing validation checks (status, validity period, usage limits, plan type restrictions).
3. WHEN a User attempts to apply an Unrestricted_Coupon, THE Coupon_Service SHALL apply no user-restriction check and proceed with existing validation logic unchanged.

---

### Requirement 4: Admin API — Add Users to Coupon Allowlist

**User Story:** As an administrator, I want to add users to a coupon's allowlist by user ID or phone number, so that I can grant access to restricted coupons.

#### Acceptance Criteria

1. THE Admin_Endpoint SHALL accept a `coupon_code` and a list of entries, each containing at least one of `user_id` or `mobile`.
2. WHEN a valid `coupon_code` and a non-empty list of user entries are provided, THE Admin_Endpoint SHALL insert the corresponding `coupon_allowed_users` rows and return a success response.
3. IF a `coupon_code` does not exist in the `coupons` table, THEN THE Admin_Endpoint SHALL return a 404 error with a descriptive message.
4. IF a duplicate `(coupon_id, user_id)` or `(coupon_id, mobile)` entry is submitted, THEN THE Admin_Endpoint SHALL skip the duplicate without error and return the count of newly added entries.
5. IF an entry contains neither `user_id` nor `mobile`, THEN THE Admin_Endpoint SHALL return a 422 validation error for that entry.

---

### Requirement 5: Admin API — Remove Users from Coupon Allowlist

**User Story:** As an administrator, I want to remove users from a coupon's allowlist, so that I can revoke access to restricted coupons.

#### Acceptance Criteria

1. THE Admin_Endpoint SHALL accept a `coupon_code` and a list of entries to remove, each containing at least one of `user_id` or `mobile`.
2. WHEN matching `coupon_allowed_users` rows are found, THE Admin_Endpoint SHALL delete them and return the count of removed entries.
3. IF no matching rows are found for a given entry, THEN THE Admin_Endpoint SHALL skip that entry without error.
4. IF a `coupon_code` does not exist, THEN THE Admin_Endpoint SHALL return a 404 error.

---

### Requirement 6: Admin API — View Coupon Allowlist

**User Story:** As an administrator, I want to view the allowlist for a coupon, so that I can audit which users have access.

#### Acceptance Criteria

1. WHEN a valid `coupon_code` is provided, THE Admin_Endpoint SHALL return all `coupon_allowed_users` rows for that coupon, including `user_id` and `mobile` for each entry.
2. IF a `coupon_code` does not exist, THEN THE Admin_Endpoint SHALL return a 404 error.
3. WHEN a coupon has no allowlist entries (Unrestricted_Coupon), THE Admin_Endpoint SHALL return an empty list.

---

### Requirement 7: Backward Compatibility

**User Story:** As a developer, I want existing coupons without an allowlist to continue working for all users, so that the feature rollout does not break current functionality.

#### Acceptance Criteria

1. THE System SHALL treat any Coupon with zero `coupon_allowed_users` rows as an Unrestricted_Coupon, applying no user-restriction filter.
2. THE Coupon_Service SHALL preserve all existing validation logic (status, validity, usage limits, plan type) for both Restricted_Coupons and Unrestricted_Coupons.
3. THE System SHALL require no changes to existing coupon records or the `coupons` table schema to enable this feature.
