# Login Module Documentation

## Overview

The login module implements a phone number-based authentication system using OTP (One-Time Password) verification. It includes comprehensive rate limiting, session management, and security features to prevent abuse and ensure secure user authentication.

## Architecture

### Components

1. **OTP Module** (`Login_module/OTP/`)
   - OTP generation and storage (Redis)
   - OTP verification
   - Rate limiting and throttling
   - Audit logging

2. **Session Management** (`Login_module/Device/`)
   - Device session creation and management
   - Active session tracking
   - Session cleanup and deactivation

3. **User Management** (`Login_module/User/`)
   - User lookup and creation
   - Mobile number normalization

4. **Token Management** (`Login_module/Token/`)
   - Access token generation
   - Refresh token handling
   - Token expiration

5. **Rate Limiting** (`Login_module/Utils/rate_limiter.py`)
   - IP-based rate limiting
   - Session-based rate limiting

---

## OTP Throttling & Rate Limiting

### 1. OTP Request Throttling

**Location**: `Login_module/OTP/otp_manager.py`

**Mechanism**:
- **Per-phone rate limit**: Maximum `OTP_MAX_REQUESTS_PER_HOUR` (default: 15) requests per hour per phone number
- **Redis-based counter**: Uses Redis key `otp_req:{country_code}:{mobile}` with 3600 seconds TTL
- **Fail-closed security**: If Redis is unavailable, OTP requests are **denied** (security-first approach)

**Implementation**:
```python
def can_request_otp(country_code: str, mobile: str) -> bool:
    # Counter expires in 3600 seconds (1 hour)
    # Returns False if limit exceeded or Redis is down
```

**Configuration** (from `config.py`):
- `OTP_MAX_REQUESTS_PER_HOUR`: 15 requests per hour per phone number
- Counter resets automatically after 1 hour

### 2. OTP Verification Rate Limiting

**Location**: `Login_module/Utils/rate_limiter.py`

**IP-based Rate Limiting**:
- **Per-IP limit**: Maximum `VERIFY_OTP_MAX_ATTEMPTS_PER_IP` (default: 10) verification attempts per hour per IP address
- **Window**: `VERIFY_OTP_WINDOW_SECONDS` (default: 3600 seconds = 1 hour)
- **Redis key**: `ip_rate_limit:verify_otp:{ip}`
- **Fail-closed**: Denies requests if Redis is unavailable

**Implementation**:
```python
def check_ip_rate_limit(ip: str) -> tuple[bool, int]:
    # Returns (is_allowed, remaining_attempts)
    # Returns (False, 0) if Redis is down (fail-closed)
```

**Configuration**:
- `VERIFY_OTP_MAX_ATTEMPTS_PER_IP`: 10 attempts per hour per IP
- `VERIFY_OTP_WINDOW_SECONDS`: 3600 seconds (1 hour)

### 3. Failed Attempt Tracking & Blocking

**Location**: `Login_module/OTP/otp_manager.py`

**Mechanism**:
- **Failed attempt counter**: Tracks failed OTP verifications per phone number
- **Block threshold**: After `OTP_MAX_FAILED_ATTEMPTS` (default: 5) failed attempts, user is blocked
- **Block duration**: `OTP_BLOCK_DURATION_SECONDS` (default: 600 seconds = 10 minutes)
- **Redis keys**:
  - `otp_failed:{country_code}:{mobile}` - Failed attempt counter (expires in 1 hour)
  - `otp_blocked:{country_code}:{mobile}` - Block status (expires after block duration)

**Implementation**:
```python
def record_failed_attempt(country_code: str, mobile: str) -> int:
    # Increments failed counter
    # Blocks user if threshold reached
    # Returns current failed count

def is_user_blocked(country_code: str, mobile: str) -> bool:
    # Checks if user is currently blocked

def reset_failed_attempts(country_code: str, mobile: str):
    # Called on successful verification
```

**Configuration**:
- `OTP_MAX_FAILED_ATTEMPTS`: 5 failed attempts before blocking
- `OTP_BLOCK_DURATION_SECONDS`: 600 seconds (10 minutes)

### 4. OTP Expiration

- **OTP validity**: `OTP_EXPIRY_SECONDS` (default: 120 seconds = 2 minutes)
- **Storage**: Redis with automatic expiration
- **Redis key**: `otp:{country_code}:{mobile}`

---

## Session Management

### Session Creation

**Location**: `Login_module/Device/Device_session_crud.py`

**Process**:
1. **Active session check**: Queries existing active sessions for the user
2. **Session limit enforcement**: If `MAX_ACTIVE_SESSIONS` (default: 4) is reached, oldest sessions are deleted
3. **Token generation**: Generates unique 32-byte URL-safe session token
4. **Session storage**: Creates `DeviceSession` record in database
5. **Audit logging**: Creates session audit log entry

**Key Features**:
- **Pessimistic locking**: Uses `with_for_update()` to prevent race conditions
- **Oldest-first deletion**: When limit reached, deletes sessions by `last_active` ascending order
- **Token uniqueness**: Retries up to 5 times to generate unique token
- **Correlation ID**: Tracks requests across services

**Configuration**:
- `MAX_ACTIVE_SESSIONS`: 4 active sessions per user
- `ACCESS_TOKEN_EXPIRE_SECONDS`: 900 seconds (15 minutes) - access token lifetime
- `MAX_SESSION_LIFETIME_DAYS`: 7 days - absolute maximum session lifetime

### Session Deactivation

**Methods**:
1. **By session ID**: `deactivate_session(session_id, reason, ...)`
2. **By token**: `deactivate_session_by_token(session_token)`

**Process**:
- Sets `is_active = False`
- Records `event_on_logout` timestamp
- Creates audit log entry
- Commits transaction

### Session Cleanup

**Location**: `Login_module/Device/Device_session_crud.py`

**Functions**:
- `cleanup_inactive_sessions(hours_inactive=24)`: Deletes inactive sessions older than threshold
- Automatic cleanup of stale sessions based on `last_active` timestamp

---

## Edge Cases & Error Handling

### 1. Redis Unavailability

**OTP Storage**:
- **Behavior**: Raises `redis.ConnectionError` if Redis is unavailable
- **Impact**: OTP cannot be stored, request fails
- **Logging**: Error logged, but app continues running

**OTP Request Throttling**:
- **Behavior**: **Fail-closed** - Returns `False` (denies request)
- **Rationale**: Security-first approach - prevents abuse when rate limiting unavailable
- **Logging**: Error logged, request denied

**OTP Verification Rate Limiting**:
- **Behavior**: **Fail-closed** - Returns `(False, 0)` (denies request)
- **Rationale**: Prevents brute force attacks when rate limiting unavailable

**Failed Attempt Tracking**:
- **Behavior**: **Fail-open** - Returns `OTP_MAX_FAILED_ATTEMPTS` (assumes max reached)
- **Rationale**: Conservative approach - assumes worst case for security

**Block Status Check**:
- **Behavior**: **Fail-open** - Returns `False` (not blocked)
- **Rationale**: Don't block legitimate users if Redis is down

### 2. User Lookup & Creation

**Location**: `Login_module/User/user_session_crud.py`

**Multi-level Fallback Strategy**:

1. **Primary lookup**: Exact match on normalized mobile number
   ```python
   user = db.query(User).filter(User.mobile == mobile_normalized).first()
   ```

2. **Normalized search**: Iterates all users, compares normalized phone numbers
   - Exact match comparison
   - Last 10 digits match (for numbers with country codes)

3. **User creation**: If no user found, attempts to create new user
   - Handles `IntegrityError` (duplicate user created concurrently)
   - Retries lookup after creation failure

4. **Final fallback**: If creation fails, performs final search through all users
   - Exact match
   - Last 10 digits match

**Edge Cases Handled**:
- **Concurrent user creation**: Handles `IntegrityError` by retrying lookup
- **Phone number format variations**: Normalizes and compares multiple ways
- **Database session expiration**: Calls `db.expire_all()` to refresh session
- **Transaction rollback**: Rolls back on critical errors

### 3. Session Creation Failures

**Edge Cases**:
- **Session ID not generated**: Validates `session.id` exists after commit
- **Session ID not integer**: Validates session ID can be converted to integer
- **Token collision**: Retries up to 5 times to generate unique token
- **Database errors**: Rolls back transaction, logs error, raises HTTPException

**Error Handling**:
```python
if not session or not session.id:
    db.rollback()
    raise HTTPException(status_code=500, detail="Session creation failed")
```

### 4. OTP Verification Edge Cases

**Bypass Code**:
- **Special OTP**: "1234" always works for any phone number
- **Use case**: Development/testing
- **Audit logging**: Logs bypass usage with IP address

**OTP Expiration**:
- **Check**: Verifies OTP exists in Redis before comparison
- **Error**: Returns 400 with message "The OTP code has expired. Please request a new one."

**Invalid OTP**:
- **Check**: Compares provided OTP with stored OTP (plaintext comparison)
- **Error**: Returns 400 with message "The OTP code you entered is incorrect. Please try again."
- **Failed attempt tracking**: Records failed attempt, may block user after threshold

**OTP Deletion**:
- **After successful verification**: OTP is deleted from Redis (single-use)
- **Exception**: Bypass code does not delete OTP (no OTP stored for bypass)

### 5. IP Address Extraction

**Location**: `Login_module/Utils/rate_limiter.py`

**Priority Order**:
1. `X-Forwarded-For` header (first IP in chain)
2. `X-Real-IP` header
3. Direct client IP from request
4. Fallback: "unknown"

**Edge Cases**:
- **Missing headers**: Falls back to direct client IP
- **Multiple IPs in X-Forwarded-For**: Takes first IP (original client)
- **Unknown IP**: Returns "unknown", rate limiting allows request (fail-open for unknown IPs)

---

## Known Bugs & Issues

### 1. Redis Connection Handling

**Issue**: Redis connection is initialized lazily, but error handling may not catch all edge cases.

**Location**: `Login_module/OTP/otp_manager.py`

**Potential Problems**:
- Race conditions during Redis reconnection
- Connection pool exhaustion not handled
- Health check interval may not catch all failures

**Mitigation**:
- Health check interval set to 30 seconds
- Connection pool size: 50 connections
- Retry on timeout enabled

### 2. User Lookup Performance

**Issue**: Final fallback search iterates through all users in database.

**Location**: `Login_module/User/user_session_crud.py`

**Problem**:
- `all_users = db.query(User).all()` loads all users into memory
- Performance degrades with large user base
- No pagination or limit

**Impact**: 
- Slow response times for large databases
- High memory usage
- Database load

**Recommendation**: 
- Add database index on `mobile` column
- Remove fallback search or add limit
- Use database-level search with proper indexing

### 3. Session Token Collision

**Issue**: Token generation retries only 5 times.

**Location**: `Login_module/Device/Device_session_crud.py`

**Problem**:
- If 5 retries all collide (extremely unlikely but possible), raises exception
- No exponential backoff or additional retry strategy

**Impact**: 
- Login failure in edge case
- User must retry login

**Mitigation**: 
- 32-byte URL-safe token has extremely low collision probability
- 5 retries should be sufficient in practice

### 4. Transaction Management

**Issue**: Some database operations may not be properly wrapped in transactions.

**Location**: Multiple files

**Potential Problems**:
- Partial commits on errors
- Nested transaction handling
- Rollback not called in all error paths

**Current Handling**:
- Explicit `db.rollback()` calls in error handlers
- `db.commit()` after successful operations
- `db.expire_all()` to refresh stale sessions

### 5. OTP Bypass Code Security

**Issue**: Hardcoded bypass code "1234" works for any phone number.

**Location**: `Login_module/OTP/OTP_router.py`

**Security Concern**:
- Bypass code should be disabled in production
- No environment-based toggle
- Always active regardless of environment

**Recommendation**:
- Add environment variable to enable/disable bypass
- Disable in production environments
- Add additional logging/alerting for bypass usage

### 6. Rate Limiting Fail-Closed Behavior

**Issue**: When Redis is unavailable, legitimate users are denied access.

**Location**: `Login_module/OTP/otp_manager.py`, `Login_module/Utils/rate_limiter.py`

**Trade-off**:
- **Security**: Prevents abuse when rate limiting unavailable
- **Availability**: Legitimate users may be denied during Redis outages

**Current Behavior**:
- OTP requests: **Fail-closed** (denied)
- OTP verification: **Fail-closed** (denied)
- Failed attempts: **Fail-open** (assumes max reached, blocks user)

**Recommendation**:
- Consider fail-open with logging for production
- Add Redis health monitoring and alerting
- Implement circuit breaker pattern

### 7. Phone Number Normalization

**Issue**: Multiple normalization strategies may lead to inconsistent matching.

**Location**: `Login_module/User/user_session_crud.py`

**Problems**:
- Last 10 digits matching may match different users
- No validation of phone number format
- Country code handling inconsistent

**Impact**:
- Potential user account confusion
- Security risk if phone numbers overlap

**Recommendation**:
- Standardize phone number format (E.164)
- Store country code separately
- Remove last 10 digits fallback matching

### 8. Session Limit Race Condition

**Issue**: Concurrent login attempts may exceed session limit.

**Location**: `Login_module/Device/Device_session_crud.py`

**Current Mitigation**:
- Uses `with_for_update()` for pessimistic locking
- Orders by `last_active` to ensure consistent deletion

**Potential Issue**:
- Lock may not prevent all race conditions
- Multiple transactions may read same session count

**Impact**: 
- May temporarily exceed `MAX_ACTIVE_SESSIONS`
- Oldest sessions deleted on next login

---

## Configuration Reference

### Environment Variables

All configuration is loaded from `.env` file via Pydantic settings (`config.py`):

**OTP Configuration**:
- `OTP_EXPIRY_SECONDS`: OTP validity period (default: 120 seconds)
- `OTP_MAX_REQUESTS_PER_HOUR`: Max OTP requests per phone per hour (default: 15)
- `OTP_MAX_FAILED_ATTEMPTS`: Failed attempts before blocking (default: 5)
- `OTP_BLOCK_DURATION_SECONDS`: Block duration after max failures (default: 600 seconds)

**Session Configuration**:
- `MAX_ACTIVE_SESSIONS`: Maximum active sessions per user (default: 4)
- `ACCESS_TOKEN_EXPIRE_SECONDS`: Access token lifetime (default: 900 seconds)
- `MAX_SESSION_LIFETIME_DAYS`: Absolute maximum session lifetime (default: 7 days)

**Rate Limiting Configuration**:
- `VERIFY_OTP_MAX_ATTEMPTS_PER_IP`: Max verification attempts per IP per hour (default: 10)
- `VERIFY_OTP_WINDOW_SECONDS`: Rate limit window (default: 3600 seconds)
- `REFRESH_TOKEN_MAX_ATTEMPTS_PER_SESSION`: Max refresh attempts per session (default: 20)
- `REFRESH_TOKEN_WINDOW_SECONDS`: Refresh token rate limit window (default: 3600 seconds)
- `REFRESH_TOKEN_MAX_FAILED_ATTEMPTS`: Max failed refresh attempts (default: 10)

**Redis Configuration**:
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_USERNAME`: Redis username (optional)
- `REDIS_PASSWORD`: Redis password (optional)
- `REDIS_DB`: Redis database number (default: 0)

---

## Security Considerations

### 1. OTP Storage
- **Storage**: Redis (in-memory, temporary)
- **Format**: Plaintext (for fast comparison)
- **Expiration**: Automatic via Redis TTL
- **Single-use**: Deleted after successful verification

### 2. Rate Limiting
- **Multi-layer**: Phone-based, IP-based, and session-based
- **Fail-closed**: Denies requests when Redis unavailable (security-first)
- **Automatic reset**: Counters expire automatically

### 3. Session Security
- **Token generation**: Cryptographically secure random tokens (32 bytes)
- **Token uniqueness**: Validated before use
- **Session limits**: Prevents unlimited concurrent sessions
- **Session expiration**: Absolute maximum lifetime enforced

### 4. Audit Logging
- **OTP events**: All OTP generation, verification, and failures logged
- **Session events**: Session creation and deletion logged
- **No sensitive data**: OTP values not stored in audit logs
- **Correlation IDs**: Track requests across services

### 5. Error Messages
- **User-friendly**: Clear error messages for users
- **No information leakage**: Errors don't reveal system internals
- **Detailed logging**: Full details logged server-side

---

## Testing Recommendations

### 1. OTP Throttling Tests
- Test OTP request limit (15 per hour)
- Test OTP verification limit (10 per IP per hour)
- Test failed attempt blocking (5 failures = 10 minute block)
- Test Redis unavailability scenarios

### 2. Session Management Tests
- Test session limit enforcement (4 active sessions)
- Test oldest session deletion
- Test concurrent login attempts
- Test session cleanup

### 3. Edge Case Tests
- Test user lookup with various phone number formats
- Test concurrent user creation
- Test OTP expiration
- Test invalid OTP handling
- Test Redis connection failures

### 4. Security Tests
- Test brute force attack prevention
- Test rate limit bypass attempts
- Test session token uniqueness
- Test audit logging completeness

---

## Monitoring & Alerting

### Key Metrics to Monitor

1. **OTP Metrics**:
   - OTP generation rate
   - OTP verification success/failure rate
   - Failed attempt rate
   - Blocked user count

2. **Session Metrics**:
   - Active session count
   - Session creation rate
   - Session cleanup rate
   - Average session lifetime

3. **Rate Limiting Metrics**:
   - Rate limit hits (denied requests)
   - IP-based rate limit triggers
   - Phone-based rate limit triggers

4. **Redis Metrics**:
   - Redis connection status
   - Redis error rate
   - Redis latency

5. **Error Metrics**:
   - Database errors
   - Redis errors
   - User creation failures
   - Session creation failures

### Alerting Recommendations

- **Redis unavailability**: Alert immediately (affects rate limiting)
- **High failed attempt rate**: Alert on spike (potential attack)
- **High rate limit hits**: Alert on spike (potential abuse)
- **Session creation failures**: Alert on increase (system issue)
- **Database errors**: Alert on any database error

---

## Future Improvements

1. **Remove OTP Bypass Code**: Disable or make environment-based
2. **Improve User Lookup**: Add database indexes, remove fallback search
3. **Enhanced Phone Number Handling**: Standardize to E.164 format
4. **Circuit Breaker Pattern**: For Redis connection handling
5. **Rate Limiting Tuning**: Adjust based on production metrics
6. **Session Analytics**: Track session patterns and optimize limits
7. **Multi-factor Authentication**: Add additional security layers
8. **Device Fingerprinting**: Enhanced device identification

---

## Summary

The login module implements a robust, security-focused authentication system with:

- **Multi-layer rate limiting**: Phone-based, IP-based, and session-based
- **Comprehensive error handling**: Fallback strategies and transaction management
- **Session management**: Limits, cleanup, and audit logging
- **Security-first design**: Fail-closed rate limiting, audit logging, secure tokens
- **Edge case handling**: Redis failures, user lookup, concurrent operations

**Key Strengths**:
- Strong rate limiting and throttling
- Comprehensive audit logging
- Security-first approach
- Transaction safety

**Areas for Improvement**:
- User lookup performance (database indexing)
- OTP bypass code security
- Phone number normalization
- Redis fail-closed behavior tuning




