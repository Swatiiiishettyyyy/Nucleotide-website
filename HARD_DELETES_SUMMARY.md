# Hard Delete Operations Summary

This document lists all places where **hard deletes** (permanent database deletions) are still being performed in the system.

## Hard Delete Locations

### 1. CartCoupon Model - Coupon Removal
**File:** `Cart_module/coupon_service.py`
**Line:** 260
**Function:** `remove_coupon_from_cart()`
**Code:**
```python
db.delete(cart_coupon)
db.commit()
```

**Context:** When a user removes a coupon from their cart, the `CartCoupon` record is permanently deleted from the database.

**Status:** `CartCoupon` model does NOT have `is_deleted` or soft delete fields. This is a hard delete.

---

### 2. DeviceSession Model - Session Cleanup (Max Sessions)
**File:** `Login_module/Device/Device_session_crud.py`
**Line:** 44
**Function:** `create_device_session()`
**Code:**
```python
if len(active_sessions) >= max_active_sessions:
    sessions_to_delete = active_sessions[:len(active_sessions) - max_active_sessions + 1]
    for old_session in sessions_to_delete:
        db.delete(old_session)
    db.flush()
```

**Context:** When a user exceeds the maximum number of active sessions (default: 4), the oldest sessions are permanently deleted.

**Status:** `DeviceSession` uses `is_active` flag for soft deactivation, but old sessions are hard-deleted when max limit is reached.

---

### 3. DeviceSession Model - Inactive Session Cleanup
**File:** `Login_module/Device/Device_session_crud.py`
**Lines:** 223, 232
**Function:** `cleanup_inactive_sessions()`
**Code:**
```python
deleted_count = (
    db.query(DeviceSession)
    .filter(
        DeviceSession.is_active == False,
        DeviceSession.event_on_logout < cutoff
    )
    .delete()
)

stale_count = (
    db.query(DeviceSession)
    .filter(
        DeviceSession.last_active < cutoff,
        DeviceSession.is_active == True
    )
    .delete()
)
```

**Context:** Cleanup function that permanently deletes:
- Inactive sessions older than specified hours (default: 24 hours)
- Stale active sessions (sessions that haven't been active for 24+ hours)

**Status:** This is a maintenance/cleanup function that hard-deletes old sessions.

---

## Models with Soft Delete (Already Implemented)

These models use soft delete and do NOT have hard deletes:

- ✅ **Member** - Uses `is_deleted` and `deleted_at`
- ✅ **Address** - Uses `is_deleted` and `deleted_at`
- ✅ **CartItem** - Uses `is_deleted`
- ✅ **Product** - Uses `is_deleted` and `deleted_at`
- ✅ **Banner** - Uses `is_deleted` and `deleted_at`

---

## Recommendations

### Option 1: Keep Hard Deletes (Recommended for some cases)
- **CartCoupon**: Hard delete is acceptable since it's a temporary cart state. If coupon is removed, the record can be safely deleted.
- **DeviceSession (cleanup)**: Hard delete for old inactive sessions is acceptable for performance/maintenance reasons.

### Option 2: Convert to Soft Delete
If audit trail is needed:

1. **CartCoupon**: Add `is_deleted` and `deleted_at` fields, then change `db.delete()` to soft delete.

2. **DeviceSession**: 
   - For max sessions: Consider keeping hard delete (it's a performance optimization)
   - For cleanup function: Could use soft delete, but hard delete may be preferred for maintenance

---

## Notes

- The `fix_alembic_to_34.py` and `fix_alembic_version.py` files contain hard deletes for the `alembic_version` table, but these are utility scripts for fixing Alembic state issues and are not part of the main application flow.
- Redis OTP deletions (in `otp_manager.py`) are not database deletions, they're cache cleanup operations.
- Google Calendar deletions are external API calls, not database operations.

