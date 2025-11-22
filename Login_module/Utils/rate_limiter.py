"""
IP-based rate limiting for OTP verification endpoint.
Prevents brute force attacks from the same IP address.
"""
import redis
import logging
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

# Import will be done after otp_manager is initialized
_redis_client = None

def _get_redis_client():
    """Lazy import to avoid circular dependency"""
    global _redis_client
    if _redis_client is None:
        from Login_module.OTP import otp_manager
        _redis_client = otp_manager._redis_client
    return _redis_client

# Rate limiting configuration
VERIFY_OTP_MAX_ATTEMPTS_PER_IP = int(os.getenv("VERIFY_OTP_MAX_ATTEMPTS_PER_IP", 10))  # 10 attempts per hour per IP
VERIFY_OTP_WINDOW_SECONDS = int(os.getenv("VERIFY_OTP_WINDOW_SECONDS", 3600))  # 1 hour


def _ip_rate_limit_key(ip: str) -> str:
    """Generate Redis key for IP-based rate limiting"""
    return f"ip_rate_limit:verify_otp:{ip}"


def check_ip_rate_limit(ip: str) -> tuple[bool, int]:
    """
    Check if IP address has exceeded rate limit for OTP verification.
    Returns (is_allowed, remaining_attempts)
    """
    if not ip or ip == "unknown":
        return True, VERIFY_OTP_MAX_ATTEMPTS_PER_IP
    
    try:
        redis_client = _get_redis_client()
        key = _ip_rate_limit_key(ip)
        attempts = redis_client.get(key)
        
        if attempts is None:
            # First attempt, set counter with expiry
            redis_client.set(key, 1, ex=VERIFY_OTP_WINDOW_SECONDS)
            return True, VERIFY_OTP_MAX_ATTEMPTS_PER_IP - 1
        
        attempts = int(attempts)
        if attempts >= VERIFY_OTP_MAX_ATTEMPTS_PER_IP:
            return False, 0
        
        # Increment counter
        redis_client.incr(key)
        remaining = VERIFY_OTP_MAX_ATTEMPTS_PER_IP - attempts - 1
        return True, max(0, remaining)
    except Exception as e:
        logger.error(f"Redis error checking IP rate limit: {e}")
        # Fail closed for security - deny if Redis is down
        return False, 0


def get_client_ip(request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"

