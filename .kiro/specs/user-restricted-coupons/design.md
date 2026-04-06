# Design Document: User-Restricted Coupons

## Overview

This feature adds an optional per-coupon user allowlist. When a coupon has one or more entries in the new `coupon_allowed_users` table it becomes a **Restricted Coupon** — only the listed users can see or apply it. Coupons with no allowlist entries remain **Unrestricted** and behave exactly as today.

The change is purely additive: no existing coupon records or the `coupons` table schema are modified. The feature is enabled by:

1. A new `CouponAllowedUser` SQLAlchemy model + Alembic migration.
2. A helper function `is_user_allowed_for_coupon()` in `coupon_service.py`.
3. A filter added to the existing `list-coupons` endpoint.
4. A guard added early in `validate_and_calculate_discount()`.
5. Three new admin endpoints for allowlist management.

---

## Architecture

```mermaid
graph TD
    A[GET /cart/list-coupons] -->|filter by allowlist| B[list_coupons()]
    C[POST /cart/apply-coupon] --> D[validate_and_calculate_discount()]
    D -->|allowlist check| E[is_user_allowed_for_coupon()]
    E --> F[(coupon_allowed_users)]
    F --> G[(coupons)]

    H[POST /admin/coupons/allowlist/add] --> I[add_allowlist_entries()]
    J[DELETE /admin/coupons/allowlist/remove] --> K[remove_allowlist_entries()]
    L[GET /admin/coupons/allowlist] --> M[get_allowlist()]
    I & K & M --> F
```

The allowlist check is a single SQL existence query. It is injected at two call sites (list and validate) and isolated in one helper so the logic is not duplicated.

---

## Components and Interfaces

### 1. `CouponAllowedUser` model (`Cart_module/Coupon_model.py`)

New SQLAlchemy model added to the existing file:

```python
class CouponAllowedUser(Base):
    __tablename__ = "coupon_allowed_users"

    id       = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id  = Column(Integer, nullable=True, index=True)
    mobile   = Column(String(100), nullable=True, index=True)

    coupon = relationship("Coupon", back_populates="allowed_users")

    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user_id"),
        UniqueConstraint("coupon_id", "mobile",  name="uq_coupon_mobile"),
        CheckConstraint("user_id IS NOT NULL OR mobile IS NOT NULL", name="ck_coupon_allowed_users_not_both_null"),
    )
```

`Coupon` gains a back-reference:

```python
allowed_users = relationship("CouponAllowedUser", back_populates="coupon", cascade="all, delete-orphan")
```

### 2. `is_user_allowed_for_coupon()` helper (`Cart_module/coupon_service.py`)

```python
def is_user_allowed_for_coupon(db: Session, coupon: Coupon, user_id: int, mobile: str) -> bool:
    """
    Returns True if the coupon is unrestricted OR the user is on the allowlist.
    A coupon is unrestricted when it has zero coupon_allowed_users rows.
    """
    from .Coupon_model import CouponAllowedUser
    count = db.query(func.count(CouponAllowedUser.id)).filter(
        CouponAllowedUser.coupon_id == coupon.id
    ).scalar() or 0
    if count == 0:
        return True  # unrestricted
    match = db.query(CouponAllowedUser).filter(
        CouponAllowedUser.coupon_id == coupon.id,
        or_(
            CouponAllowedUser.user_id == user_id,
            CouponAllowedUser.mobile == mobile
        )
    ).first()
    return match is not None
```

### 3. Changes to `validate_and_calculate_discount()` (`coupon_service.py`)

After the coupon is fetched and before the status check, insert:

```python
# User restriction check
from Login_module.User.user_model import User as _User
_user = db.query(_User).filter(_User.id == user_id).first()
_mobile = _user.mobile if _user else ""
if not is_user_allowed_for_coupon(db, coupon, user_id, _mobile):
    return None, 0.0, "Invalid coupon code."
```

The error message is intentionally generic to avoid leaking that a restricted coupon exists.

### 4. Changes to `list_coupons()` (`Cart_router.py`)

Inside the per-coupon loop, after the per-user usage check, add:

```python
if not is_user_allowed_for_coupon(db, coupon, current_user.id, current_user.mobile):
    continue
```

### 5. Admin endpoints (`Cart_router.py`)

Three new routes, all under `/admin/coupons/allowlist`:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/coupons/allowlist/add` | Add users to a coupon's allowlist |
| `DELETE` | `/admin/coupons/allowlist/remove` | Remove users from a coupon's allowlist |
| `GET` | `/admin/coupons/allowlist` | View a coupon's allowlist |

Request/response schemas (Pydantic, added to `Cart_schema.py`):

```python
class AllowlistEntry(BaseModel):
    user_id: Optional[int] = None
    mobile: Optional[str] = None

    @validator("mobile", always=True)
    def at_least_one(cls, mobile, values):
        if not values.get("user_id") and not mobile:
            raise ValueError("At least one of user_id or mobile is required")
        return mobile

class AllowlistAddRequest(BaseModel):
    coupon_code: str
    entries: List[AllowlistEntry]

class AllowlistRemoveRequest(BaseModel):
    coupon_code: str
    entries: List[AllowlistEntry]

class AllowlistEntryResponse(BaseModel):
    id: int
    coupon_id: int
    user_id: Optional[int]
    mobile: Optional[str]
```

---

## Data Models

### `coupon_allowed_users` table

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | INTEGER PK | No | Auto-increment |
| `coupon_id` | INTEGER FK | No | → `coupons.id` ON DELETE CASCADE |
| `user_id` | INTEGER | Yes | Indexed; unique with `coupon_id` |
| `mobile` | VARCHAR(100) | Yes | Indexed; unique with `coupon_id` |

Constraints:
- `CHECK (user_id IS NOT NULL OR mobile IS NOT NULL)`
- `UNIQUE (coupon_id, user_id)` — partial (only meaningful when `user_id` IS NOT NULL; enforced at app layer for NULL)
- `UNIQUE (coupon_id, mobile)` — same caveat for NULL

> Note: SQL `UNIQUE` constraints treat NULL as distinct, so two rows with `(coupon_id=1, user_id=NULL)` are technically allowed by the DB. The application layer enforces the intent by always providing at least one non-null identifier and by using upsert-skip logic in the add endpoint.

### Alembic migration

New file `031_add_coupon_allowed_users.py`, chained from `030_fix_payment_status_enum_case`:

```python
revision = "031_add_coupon_allowed_users"
down_revision = "030_fix_payment_status_enum_case"
```

`upgrade()` creates the `coupon_allowed_users` table with the FK, indexes, and check constraint.  
`downgrade()` drops the table.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Allowlist row validity

*For any* `CouponAllowedUser` row, at least one of `user_id` or `mobile` must be non-null. Attempting to insert a row where both are null must raise a constraint error.

**Validates: Requirements 1.2**

---

### Property 2: Cascade delete

*For any* coupon that has one or more `coupon_allowed_users` rows, deleting that coupon must result in zero remaining `coupon_allowed_users` rows for that coupon id.

**Validates: Requirements 1.5**

---

### Property 3: Restricted coupon visibility is allowlist-gated

*For any* active, valid, unreached-limit coupon that has at least one allowlist entry, and *for any* user whose `user_id` and `mobile` are both absent from that allowlist, the `list-coupons` response must not contain that coupon. Conversely, if the user's `user_id` or `mobile` appears in the allowlist, the coupon must be present (assuming it passes all other checks).

**Validates: Requirements 2.1, 2.3, 2.4**

---

### Property 4: Unrestricted coupons are always visible

*For any* active, valid, unreached-limit coupon with zero allowlist entries, and *for any* authenticated user, the coupon must appear in the `list-coupons` response.

**Validates: Requirements 2.2, 7.1**

---

### Property 5: Allowlist check gates coupon application

*For any* restricted coupon and *for any* user whose `user_id` and `mobile` are both absent from the allowlist, `validate_and_calculate_discount()` must return `(None, 0.0, <non-empty error string>)`. For a user who is on the allowlist, the function must proceed to the existing validation checks (status, validity, usage limits, plan type) and not short-circuit on the allowlist check.

**Validates: Requirements 3.1, 3.2**

---

### Property 6: Unrestricted coupon validation is unchanged

*For any* coupon with zero allowlist entries, the result of `validate_and_calculate_discount()` must be identical before and after this feature is deployed (i.e., the allowlist check is a no-op).

**Validates: Requirements 3.3, 7.2**

---

### Property 7: Add allowlist entries round-trip

*For any* existing coupon and *for any* non-empty list of valid entries (each with at least one of `user_id`/`mobile`), calling the add endpoint followed by the view endpoint must return a list that contains all the added entries.

**Validates: Requirements 4.2, 6.1**

---

### Property 8: Add is idempotent

*For any* existing coupon and *for any* entry already present in the allowlist, submitting that entry again via the add endpoint must not create a duplicate row, must not return an error, and must report zero newly added entries for that duplicate.

**Validates: Requirements 4.4**

---

### Property 9: Non-existent coupon returns 404

*For any* coupon code that does not exist in the `coupons` table, all three admin endpoints (add, remove, view) must return HTTP 404.

**Validates: Requirements 4.3, 5.4, 6.2**

---

### Property 10: Remove allowlist entries round-trip

*For any* coupon with a non-empty allowlist, calling the remove endpoint for all entries followed by the view endpoint must return an empty list.

**Validates: Requirements 5.2, 6.3**

---

### Property 11: Remove is a no-op for absent entries

*For any* existing coupon and *for any* entry not present in the allowlist, calling the remove endpoint must not return an error and must report zero removed entries.

**Validates: Requirements 5.3**

---

## Error Handling

| Scenario | HTTP Status | Message |
|----------|-------------|---------|
| User not on allowlist tries to apply coupon | 400 | "Invalid coupon code." (generic, no leakage) |
| Admin add/remove/view with non-existent coupon code | 404 | "Coupon '{code}' not found." |
| Admin add entry with both `user_id` and `mobile` null | 422 | Pydantic validation error |
| DB constraint violation on duplicate insert | Handled at app layer — skip silently | — |
| Unexpected DB error | 500 | Generic retry message |

The allowlist check in `validate_and_calculate_discount()` returns the same generic "Invalid coupon code." message used for non-existent coupons. This prevents an attacker from probing which coupons exist but are restricted.

---

## Testing Strategy

### Unit tests

Focus on specific examples and edge cases:

- Verify `CouponAllowedUser` table schema (columns, FK, constraints exist).
- Verify that inserting a row with both `user_id=None` and `mobile=None` raises an integrity error.
- Verify that deleting a `Coupon` cascades to its `coupon_allowed_users` rows.
- Verify admin add endpoint returns 404 for a non-existent coupon code.
- Verify admin add endpoint returns 422 when an entry has neither `user_id` nor `mobile`.
- Verify `list-coupons` returns an empty list when the only active coupon is restricted and the user is not on the allowlist.
- Verify the `coupons` table schema is unchanged (no new columns).

### Property-based tests

Use **Hypothesis** (Python) for all property tests. Configure each test with `@settings(max_examples=100)`.

Each test is tagged with a comment in the format:
`# Feature: user-restricted-coupons, Property N: <property text>`

| Property | Test description |
|----------|-----------------|
| P1 | Generate random `(user_id, mobile)` pairs where both are None; assert DB raises IntegrityError |
| P2 | Generate random coupon + N allowlist entries; delete coupon; assert count of allowlist rows = 0 |
| P3 | Generate random restricted coupon + random user not on allowlist; assert coupon absent from list; generate user on allowlist; assert coupon present |
| P4 | Generate random unrestricted coupon (no allowlist); assert it appears in list for any user |
| P5 | Generate random restricted coupon + random non-allowed user; assert validate returns error; generate allowed user; assert validate proceeds to next check |
| P6 | Generate random unrestricted coupon; assert validate result is same as calling the pre-feature code path |
| P7 | Generate random coupon + random valid entries; add via endpoint; view via endpoint; assert all entries present |
| P8 | Generate random coupon + random entry; add twice; assert row count = 1 and second call reports 0 new entries |
| P9 | Generate random non-existent coupon code; call all three admin endpoints; assert all return 404 |
| P10 | Generate random coupon + random entries; add all; remove all; view; assert empty list |
| P11 | Generate random coupon + random entry not in allowlist; remove; assert no error and 0 removed |

Both unit and property tests live in `Cart_module/tests/test_coupon_allowlist.py`.
