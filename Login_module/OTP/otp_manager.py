import secrets
from typing import Optional
from dotenv import load_dotenv
import os
import redis
import logging

# Load .env file
load_dotenv()

# Read OTP-related environment variables
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 120))  # 2 minutes
OTP_MAX_REQUESTS_PER_HOUR = int(os.getenv("OTP_MAX_REQUESTS_PER_HOUR", 15))  # 15 per hour
OTP_MAX_FAILED_ATTEMPTS = int(os.getenv("OTP_MAX_FAILED_ATTEMPTS", 5))  # Block after 5 failed attempts
OTP_BLOCK_DURATION_SECONDS = int(os.getenv("OTP_BLOCK_DURATION_SECONDS", 600))  # 10 minutes block

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_DB = int(os.getenv("REDIS_DB", 0))

logger = logging.getLogger(__name__)

# Initialize Redis connection
try:
    _redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
        max_connections=50,  # Connection pool size
        socket_keepalive=True
    )
    # Test connection
    _redis_client.ping()
    logger.info(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.ConnectionError as e:
    logger.error(f"❌ Redis connection failed: {e}")
    raise
except redis.AuthenticationError as e:
    logger.error(f"❌ Redis authentication failed: {e}")
    raise
except Exception as e:
    logger.error(f"❌ Redis initialization error: {e}")
    raise


def _otp_key(country_code: str, mobile: str) -> str:
    return f"otp:{country_code}:{mobile}"


def _otp_req_key(country_code: str, mobile: str) -> str:
    return f"otp_req:{country_code}:{mobile}"


def _otp_failed_key(country_code: str, mobile: str) -> str:
    """Key for tracking failed OTP attempts"""
    return f"otp_failed:{country_code}:{mobile}"


def _otp_blocked_key(country_code: str, mobile: str) -> str:
    """Key for tracking blocked users"""
    return f"otp_blocked:{country_code}:{mobile}"


def generate_otp(length: int = 4) -> str:
    # numeric OTP
    return "".join(secrets.choice("0123456789") for _ in range(length))


def store_otp(country_code: str, mobile: str, otp: str, expires_in: int = None):
    """Store OTP in Redis with TTL"""
    try:
        key = _otp_key(country_code, mobile)
        ex = expires_in or OTP_EXPIRY_SECONDS
        _redis_client.set(key, otp, ex=ex)
    except redis.RedisError as e:
        logger.error(f"Redis error storing OTP: {e}")
        raise


def get_otp(country_code: str, mobile: str) -> Optional[str]:
    """Get OTP from Redis"""
    try:
        return _redis_client.get(_otp_key(country_code, mobile))
    except redis.RedisError as e:
        logger.error(f"Redis error getting OTP: {e}")
        return None


def delete_otp(country_code: str, mobile: str):
    """Delete OTP from Redis"""
    try:
        _redis_client.delete(_otp_key(country_code, mobile))
    except redis.RedisError as e:
        logger.error(f"Redis error deleting OTP: {e}")


def can_request_otp(country_code: str, mobile: str) -> bool:
    """
    Rate limiting per-hour by storing a counter that expires in 3600 seconds.
    For security operations, we fail closed if Redis is down.
    """
    try:
        req_key = _otp_req_key(country_code, mobile)
        cnt = _redis_client.get(req_key)
        if cnt is None:
            # seed counter with expiry 3600
            _redis_client.set(req_key, 1, ex=3600)
            return True
        if int(cnt) >= OTP_MAX_REQUESTS_PER_HOUR:
            return False
        _redis_client.incr(req_key)
        return True
    except redis.RedisError as e:
        logger.error(f"Redis error checking OTP request limit: {e}")
        # Fail closed for security - deny if Redis is down
        return False


def get_remaining_requests(country_code: str, mobile: str) -> int:
    try:
        req_key = _otp_req_key(country_code, mobile)
        cnt = _redis_client.get(req_key)
        if cnt is None:
            return OTP_MAX_REQUESTS_PER_HOUR
        return max(0, OTP_MAX_REQUESTS_PER_HOUR - int(cnt))
    except redis.RedisError as e:
        logger.error(f"Redis error getting remaining requests: {e}")
        return OTP_MAX_REQUESTS_PER_HOUR


def is_user_blocked(country_code: str, mobile: str) -> bool:
    """Check if user is blocked due to too many failed attempts"""
    try:
        block_key = _otp_blocked_key(country_code, mobile)
        blocked = _redis_client.get(block_key)
        return blocked is not None
    except redis.RedisError as e:
        logger.error(f"Redis error checking user block status: {e}")
        return False  # Fail open - don't block if Redis is down


def get_block_remaining_time(country_code: str, mobile: str) -> int:
    """Get remaining block time in seconds, or 0 if not blocked"""
    try:
        block_key = _otp_blocked_key(country_code, mobile)
        ttl = _redis_client.ttl(block_key)
        return max(0, ttl) if ttl > 0 else 0
    except redis.RedisError as e:
        logger.error(f"Redis error getting block remaining time: {e}")
        return 0


def record_failed_attempt(country_code: str, mobile: str) -> int:
    """
    Record a failed OTP attempt and return current failed count.
    If threshold reached, block the user.
    """
    try:
        failed_key = _otp_failed_key(country_code, mobile)
        failed_count = _redis_client.get(failed_key)
        
        if failed_count is None:
            # First failed attempt, set with 1 hour expiry
            _redis_client.set(failed_key, 1, ex=3600)
            failed_count = 1
        else:
            failed_count = int(failed_count) + 1
            _redis_client.set(failed_key, failed_count, ex=3600)
        
        # Block user if threshold reached
        if failed_count >= OTP_MAX_FAILED_ATTEMPTS:
            block_key = _otp_blocked_key(country_code, mobile)
            _redis_client.set(block_key, True, ex=OTP_BLOCK_DURATION_SECONDS)
            # Reset failed count after blocking
            _redis_client.delete(failed_key)
        
        return failed_count
    except redis.RedisError as e:
        logger.error(f"Redis error recording failed attempt: {e}")
        # For security, assume max attempts reached if Redis is down
        return OTP_MAX_FAILED_ATTEMPTS


def reset_failed_attempts(country_code: str, mobile: str):
    """Reset failed attempts counter (called on successful verification)"""
    try:
        failed_key = _otp_failed_key(country_code, mobile)
        _redis_client.delete(failed_key)
    except redis.RedisError as e:
        logger.error(f"Redis error resetting failed attempts: {e}")