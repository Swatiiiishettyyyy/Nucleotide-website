import time
import threading
import secrets
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Read OTP-related environment variables
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))
OTP_MAX_REQUESTS_PER_HOUR = int(os.getenv("OTP_MAX_REQUESTS_PER_HOUR", 5))


class _FakeRedis:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ex: Optional[int] = None):
        with self._lock:
            self._store[key] = {"value": value}
            if ex:
                self._store[key]["expires_at"] = time.time() + ex
            else:
                self._store[key]["expires_at"] = None

    def get(self, key: str):
        with self._lock:
            v = self._store.get(key)
            if not v:
                return None
            expires_at = v.get("expires_at")
            if expires_at and time.time() > expires_at:
                # expired
                del self._store[key]
                return None
            return v["value"]

    def delete(self, key: str):
        with self._lock:
            if key in self._store:
                del self._store[key]

    def incr(self, key: str):
        with self._lock:
            v = self._store.get(key)
            if not v:
                self._store[key] = {"value": 1, "expires_at": None}
                return 1
            self._store[key]["value"] = int(self._store[key]["value"]) + 1
            return self._store[key]["value"]

    def ttl(self, key: str):
        with self._lock:
            v = self._store.get(key)
            if not v:
                return -2
            if v["expires_at"] is None:
                return -1
            return int(v["expires_at"] - time.time())


# single instance
_fake_redis = _FakeRedis()


def _otp_key(country_code: str, mobile: str) -> str:
    return f"otp:{country_code}:{mobile}"


def _otp_req_key(country_code: str, mobile: str) -> str:
    return f"otp_req:{country_code}:{mobile}"


def generate_otp(length: int = 6) -> str:
    # numeric OTP
    return "".join(secrets.choice("0123456789") for _ in range(length))


def store_otp(country_code: str, mobile: str, otp: str, expires_in: int = None):
    key = _otp_key(country_code, mobile)
    ex = expires_in or OTP_EXPIRY_SECONDS
    _fake_redis.set(key, otp, ex=ex)


def get_otp(country_code: str, mobile: str) -> Optional[str]:
    return _fake_redis.get(_otp_key(country_code, mobile))


def delete_otp(country_code: str, mobile: str):
    _fake_redis.delete(_otp_key(country_code, mobile))


def can_request_otp(country_code: str, mobile: str) -> bool:
    """
    Rate limiting per-hour by storing a counter that expires in 3600 seconds.
    """
    req_key = _otp_req_key(country_code, mobile)
    cnt = _fake_redis.get(req_key)
    if cnt is None:
        # seed counter with expiry 3600
        _fake_redis.set(req_key, 1, ex=3600)
        return True
    if int(cnt) >= OTP_MAX_REQUESTS_PER_HOUR:
        return False
    _fake_redis.incr(req_key)
    return True


def get_remaining_requests(country_code: str, mobile: str) -> int:
    req_key = _otp_req_key(country_code, mobile)
    cnt = _fake_redis.get(req_key)
    if cnt is None:
        return OTP_MAX_REQUESTS_PER_HOUR
    return max(0, OTP_MAX_REQUESTS_PER_HOUR - int(cnt))