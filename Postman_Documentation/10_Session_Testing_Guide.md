# Guide: Testing Multiple Sessions, Rate Limits, and Blocks

## Overview
This guide explains how to test multiple sessions for the same user and how the rate limiting and blocking mechanisms work to avoid triggering them during testing.

---

## How to Get Multiple Sessions of the Same User

### Method 1: Login from Different Devices/Browsers (Recommended)

Each login creates a new session. To get multiple sessions:

1. **Use different browsers:**
   - Chrome: Session 1
   - Firefox: Session 2
   - Edge: Session 3
   - Safari: Session 4

2. **Use different devices:**
   - Desktop: Session 1
   - Mobile: Session 2
   - Tablet: Session 3
   - Another device: Session 4

3. **Use different device IDs:**
   - Each device should have a unique `device_id` in the request

### Step-by-Step Process

1. **Send OTP** (same phone number from different sources):
   ```json
   POST /auth/send-otp
   {
     "country_code": "+91",
     "mobile": "9876543210",
     "device_id": "device-chrome-1",
     "device_platform": "web",
     "device_details": "Chrome on Windows"
   }
   ```

2. **Verify OTP and get token**:
   ```json
   POST /auth/verify-otp
   {
     "country_code": "+91",
     "mobile": "9876543210",
     "otp": "123456",
     "device_id": "device-chrome-1",
     "device_platform": "web"
   }
   ```
   **Save this token as Session 1**

3. **Repeat from a different browser/device:**
   - Use a different `device_id` (e.g., "device-firefox-1", "device-mobile-1")
   - Use a different `device_platform` (e.g., "mobile", "ios", "android")
   - Use different `device_details` or `user_agent`
   - Get OTP again (you'll get a new OTP)
   - Verify with the new OTP
   - **Save this token as Session 2**

4. **Repeat for Session 3 and Session 4** (up to 4 sessions maximum)

### Method 2: Use Different IP Addresses

If you want to test from the same device but different IPs:

1. **Use VPN or Proxy:**
   - Change your IP address using VPN
   - Send OTP from new IP
   - Verify OTP
   - Each IP change can help bypass IP-based rate limits

2. **Use Mobile Data vs WiFi:**
   - WiFi IP: Session 1
   - Mobile Data IP: Session 2

### Method 3: Use Postman with Different Headers

In Postman, you can simulate different devices by changing headers:

1. **Create multiple requests** with different headers:
   ```
   User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/1
   X-Forwarded-For: 192.168.1.100
   ```

2. **Create another request** with different headers:
   ```
   User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 14_0) Mobile/1
   X-Forwarded-For: 192.168.1.101
   ```

**Note:** The IP address is extracted from `X-Forwarded-For` or `X-Real-IP` headers first, then from `request.client.host`.

---

## Understanding Rate Limits and Blocks

### 1. IP-Based Rate Limiting (for OTP Verification)

**What it does:**
- Limits the number of OTP verification attempts **per IP address**
- Prevents brute force attacks from the same IP

**Configuration:**
- Default: **10 attempts per hour per IP**
- Configurable via `VERIFY_OTP_MAX_ATTEMPTS_PER_IP` environment variable
- Window: 1 hour (3600 seconds)
- Configurable via `VERIFY_OTP_WINDOW_SECONDS` environment variable

**How it works:**
1. Redis stores a counter: `ip_rate_limit:verify_otp:{ip_address}`
2. Each verification attempt increments the counter
3. Counter expires after 1 hour
4. After 10 attempts, IP is rate-limited for 1 hour

**What happens when limit is reached:**
- Error: `429 Too Many Requests`
- Message: "Too many verification attempts from this IP. Please try again later."
- You must wait 1 hour OR use a different IP address

**Redis Key Format:**
```
ip_rate_limit:verify_otp:{ip_address}
```

**How to check in Redis:**
```bash
redis-cli
GET ip_rate_limit:verify_otp:192.168.1.100
TTL ip_rate_limit:verify_otp:192.168.1.100
```

**How to bypass for testing:**
1. Use different IP addresses (VPN, proxy)
2. Change `X-Forwarded-For` header in requests
3. Wait 1 hour for counter to reset
4. Delete the Redis key manually:
   ```bash
   redis-cli DEL ip_rate_limit:verify_otp:192.168.1.100
   ```

---

### 2. OTP Request Rate Limiting (per phone number)

**What it does:**
- Limits how many times a phone number can **request an OTP** per hour
- Prevents OTP spam

**Configuration:**
- Default: **15 requests per hour per phone number**
- Configurable via `OTP_MAX_REQUESTS_PER_HOUR` environment variable
- Window: 1 hour (3600 seconds)

**How it works:**
1. Redis stores a counter: `otp_req:{country_code}:{mobile}`
2. Each OTP request increments the counter
3. Counter expires after 1 hour
4. After 15 requests, phone number cannot request more OTPs for 1 hour

**What happens when limit is reached:**
- Error: `429 Too Many Requests`
- Message: "OTP request limit reached. Remaining: 0"
- You must wait 1 hour OR use a different phone number

**Redis Key Format:**
```
otp_req:{country_code}:{mobile}
```

**How to check in Redis:**
```bash
redis-cli
GET otp_req:+91:9876543210
TTL otp_req:+91:9876543210
```

**How to bypass for testing:**
1. Use a different phone number
2. Wait 1 hour for counter to reset
3. Delete the Redis key manually:
   ```bash
   redis-cli DEL otp_req:+91:9876543210
   ```

---

### 3. User Blocking (for failed OTP attempts)

**What it does:**
- Blocks a phone number after too many **failed OTP verification attempts**
- Prevents brute force attacks on a specific account

**Configuration:**
- Default: **5 failed attempts** trigger a block
- Configurable via `OTP_MAX_FAILED_ATTEMPTS` environment variable
- Block duration: **10 minutes** (600 seconds)
- Configurable via `OTP_BLOCK_DURATION_SECONDS` environment variable

**How it works:**
1. Redis stores failed attempt counter: `otp_failed:{country_code}:{mobile}`
2. Each failed OTP verification increments the counter
3. Counter expires after 1 hour
4. After 5 failed attempts, user is blocked
5. Redis stores block flag: `otp_blocked:{country_code}:{mobile}`
6. Block expires after 10 minutes
7. Failed counter is reset when block is triggered

**What happens when blocked:**
- Error: `403 Forbidden`
- Message: "Account temporarily blocked due to too many failed attempts. Try again in X minutes."
- User cannot send or verify OTP for 10 minutes

**Redis Keys:**
```
otp_failed:{country_code}:{mobile}     # Failed attempt counter
otp_blocked:{country_code}:{mobile}    # Block flag (TTL = block duration)
```

**How to check in Redis:**
```bash
redis-cli
GET otp_failed:+91:9876543210
GET otp_blocked:+91:9876543210
TTL otp_blocked:+91:9876543210
```

**How to bypass for testing:**
1. Use correct OTP (successful verification resets failed counter)
2. Wait 10 minutes for block to expire
3. Delete the Redis keys manually:
   ```bash
   redis-cli DEL otp_failed:+91:9876543210
   redis-cli DEL otp_blocked:+91:9876543210
   ```

---

## Complete Testing Workflow (Avoiding Rate Limits and Blocks)

### Scenario: Test Multiple Sessions for Same User

**Step 1: Setup (One-time)**
1. Ensure Redis is running
2. Have test phone numbers ready (or prepare to clear Redis keys)

**Step 2: Create Session 1**
```bash
# Request OTP
POST /auth/send-otp
{
  "country_code": "+91",
  "mobile": "9876543210",
  "device_id": "test-device-1",
  "device_platform": "web"
}

# Verify OTP (save token)
POST /auth/verify-otp
{
  "country_code": "+91",
  "mobile": "9876543210",
  "otp": "<otp_from_response>",
  "device_id": "test-device-1",
  "device_platform": "web"
}
```

**Step 3: Create Session 2**
- Change `device_id` to "test-device-2"
- Change `device_platform` to "mobile"
- Request new OTP (you'll get a different OTP)
- Verify with new OTP
- Save the new token

**Step 4: Create Session 3 and 4**
- Repeat with different `device_id` and `device_platform`
- Use different `device_details` or `user_agent`

**Step 5: Check Active Sessions**
```bash
GET /sessions/active
Authorization: Bearer <any_session_token>

# Response shows all 4 sessions
```

**Step 6: Create Session 5 (should remove oldest)**
- When you create a 5th session, the oldest session (by `last_active`) is automatically removed
- You'll still have 4 active sessions

---

## Testing Different IP Addresses (Avoiding IP Rate Limit)

### Method 1: Change X-Forwarded-For Header

In Postman, add a custom header:
```
X-Forwarded-For: 192.168.1.100
```

For different requests, use different IPs:
- Request 1: `X-Forwarded-For: 192.168.1.100`
- Request 2: `X-Forwarded-For: 192.168.1.101`
- Request 3: `X-Forwarded-For: 192.168.1.102`

### Method 2: Use Different Networks

- WiFi Network 1: IP 192.168.1.100
- Mobile Data: IP 203.0.113.50
- WiFi Network 2: IP 192.168.1.200

### Method 3: Use VPN/Proxy

- VPN Location 1: Different IP
- VPN Location 2: Different IP
- Disable VPN: Original IP

---

## Clearing Rate Limits and Blocks Manually (For Testing)

### Clear IP Rate Limit

```bash
# Connect to Redis
redis-cli

# List all IP rate limit keys
KEYS ip_rate_limit:verify_otp:*

# Delete specific IP rate limit
DEL ip_rate_limit:verify_otp:192.168.1.100

# Delete all IP rate limits (⚠️ Use with caution)
KEYS ip_rate_limit:verify_otp:* | xargs redis-cli DEL
```

### Clear OTP Request Limit

```bash
# List all OTP request keys
KEYS otp_req:*

# Delete specific phone number limit
DEL otp_req:+91:9876543210

# Delete all OTP request limits (⚠️ Use with caution)
KEYS otp_req:* | xargs redis-cli DEL
```

### Clear User Block

```bash
# List all block keys
KEYS otp_blocked:*

# Delete specific user block
DEL otp_blocked:+91:9876543210

# Also delete failed attempts counter
DEL otp_failed:+91:9876543210

# Delete all blocks (⚠️ Use with caution)
KEYS otp_blocked:* | xargs redis-cli DEL
KEYS otp_failed:* | xargs redis-cli DEL
```

### Clear All OTP-Related Keys (⚠️ Nuclear Option)

```bash
# Clear all OTP, rate limit, and block keys
KEYS otp:* | xargs redis-cli DEL
KEYS ip_rate_limit:* | xargs redis-cli DEL
KEYS otp_req:* | xargs redis-cli DEL
KEYS otp_failed:* | xargs redis-cli DEL
KEYS otp_blocked:* | xargs redis-cli DEL
```

---

## Environment Variables for Testing

To make testing easier, you can temporarily adjust these in your `.env` file:

```env
# OTP Verification IP Rate Limit (default: 10 per hour)
VERIFY_OTP_MAX_ATTEMPTS_PER_IP=100

# IP Rate Limit Window (default: 3600 seconds = 1 hour)
VERIFY_OTP_WINDOW_SECONDS=3600

# OTP Request Limit per Phone (default: 15 per hour)
OTP_MAX_REQUESTS_PER_HOUR=100

# Failed Attempts Before Block (default: 5)
OTP_MAX_FAILED_ATTEMPTS=10

# Block Duration (default: 600 seconds = 10 minutes)
OTP_BLOCK_DURATION_SECONDS=60

# OTP Expiry (default: 120 seconds = 2 minutes)
OTP_EXPIRY_SECONDS=300

# Max Active Sessions per User (default: 4)
MAX_ACTIVE_SESSIONS=10
```

**⚠️ Warning:** These are for testing only. Use production values in production!

---

## Quick Reference: Redis Keys

| Purpose | Redis Key Format | TTL |
|---------|-----------------|-----|
| OTP Value | `otp:{country_code}:{mobile}` | OTP_EXPIRY_SECONDS (2 min) |
| OTP Request Counter | `otp_req:{country_code}:{mobile}` | 3600 sec (1 hour) |
| Failed Attempt Counter | `otp_failed:{country_code}:{mobile}` | 3600 sec (1 hour) |
| User Block Flag | `otp_blocked:{country_code}:{mobile}` | OTP_BLOCK_DURATION_SECONDS (10 min) |
| IP Rate Limit Counter | `ip_rate_limit:verify_otp:{ip}` | VERIFY_OTP_WINDOW_SECONDS (1 hour) |

---

## Common Testing Scenarios

### Scenario 1: Test 4 Sessions from Same IP
1. Use different `device_id` values
2. Use different `device_platform` values
3. Use different `user_agent` headers
4. IP rate limit allows 10 attempts/hour, so 4 logins is fine

### Scenario 2: Test IP Rate Limit
1. Make 11 verification attempts from same IP with wrong OTPs
2. 10th attempt: Should still work (at the limit)
3. 11th attempt: Should get `429 Too Many Requests`
4. Wait 1 hour OR change IP OR clear Redis key

### Scenario 3: Test User Block
1. Make 5 failed OTP verification attempts
2. 5th attempt: User gets blocked
3. Next attempt: Should get `403 Forbidden` with block message
4. Wait 10 minutes OR clear Redis keys

### Scenario 4: Test OTP Request Limit
1. Request OTP 16 times for same phone number
2. 15th request: Should still work
3. 16th request: Should get `429 Too Many Requests`
4. Wait 1 hour OR use different phone number OR clear Redis key

---

## Troubleshooting

### Issue: "Too many verification attempts from this IP"
- **Solution:** You hit the IP rate limit (10 attempts/hour)
- **Fix:** Change IP, wait 1 hour, or clear Redis key: `DEL ip_rate_limit:verify_otp:{your_ip}`

### Issue: "OTP request limit reached"
- **Solution:** You hit the OTP request limit (15 requests/hour per phone)
- **Fix:** Use different phone number, wait 1 hour, or clear Redis key: `DEL otp_req:+91:9876543210`

### Issue: "Account temporarily blocked"
- **Solution:** User is blocked due to 5 failed attempts
- **Fix:** Wait 10 minutes, or clear Redis keys: `DEL otp_blocked:+91:9876543210` and `DEL otp_failed:+91:9876543210`

### Issue: Cannot create 5th session
- **Solution:** Maximum 4 sessions per user. The oldest session is automatically removed when creating a 5th.
- **Fix:** This is expected behavior. Check `/sessions/active` to see which session was removed.

---

## Summary

1. **Multiple Sessions:** Login from different devices/browsers with different `device_id` values
2. **IP Rate Limit:** 10 verification attempts per IP per hour (bypass with different IPs)
3. **OTP Request Limit:** 15 OTP requests per phone number per hour
4. **User Block:** 5 failed attempts = 10 minute block
5. **Session Limit:** Maximum 4 active sessions per user
6. **All limits stored in Redis** - can be cleared manually for testing

