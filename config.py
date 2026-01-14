import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    # Token configuration - Dual Token Strategy
    # These can be overridden via .env file for testing:
    # ACCESS_TOKEN_EXPIRE_MINUTES=5 (5 minutes for quick testing)
    # ACCESS_TOKEN_EXPIRE_MINUTES=1440 (24 hours for extended testing)
    # ACCESS_TOKEN_EXPIRE_SECONDS=300 (5 minutes in seconds - optional, auto-calculated if not set)
    # REFRESH_TOKEN_EXPIRE_DAYS_WEB=7 (7 days for testing)
    # REFRESH_TOKEN_EXPIRE_DAYS_MOBILE=7 (7 days for testing)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Default: 15 minutes
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900  # Will be recalculated from minutes if not set in env
    # Refresh token: 7 days
    REFRESH_TOKEN_EXPIRE_DAYS_WEB: float = 7.0  # Default: 7 days
    REFRESH_TOKEN_EXPIRE_DAYS_MOBILE: float = 7.0  # Default: 7 days
    
    # Cookie configuration for web
    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool = True
    
    # CSRF protection
    CSRF_SECRET_KEY: str = ""
    
    # OTP config - can be overridden via .env
    OTP_EXPIRY_SECONDS: int = 120  # 2 minutes
    OTP_MAX_REQUESTS_PER_HOUR: int = 15  # 15 per hour
    OTP_MAX_FAILED_ATTEMPTS: int = 5  # Block after 5 failed attempts
    OTP_BLOCK_DURATION_SECONDS: int = 600  # 10 minutes block
    
    # Session management
    MAX_ACTIVE_SESSIONS: int = 4  # Max 4 active sessions per user
    
    # Refresh token rate limiting - can be overridden via .env
    REFRESH_TOKEN_MAX_ATTEMPTS_PER_SESSION: int = 20  # 20 requests per hour per session
    REFRESH_TOKEN_WINDOW_SECONDS: int = 3600  # 1 hour window
    REFRESH_TOKEN_MAX_FAILED_ATTEMPTS: int = 10  # Block after 10 failures
    
    # OTP verification rate limiting - can be overridden via .env
    VERIFY_OTP_MAX_ATTEMPTS_PER_IP: int = 10  # 10 attempts per hour per IP
    VERIFY_OTP_WINDOW_SECONDS: int = 3600  # 1 hour window
    
    # Maximum session lifetime (absolute expiration - prevents indefinite sessions)
    # Should match refresh token lifetime for consistency
    # Can be overridden via .env: MAX_SESSION_LIFETIME_DAYS=7 (7 days for production)
    MAX_SESSION_LIFETIME_DAYS: float = 7.0  # Default: 7 days

    ENVIRONMENT: str = "development"

    class Config:
        # Use absolute path to make sure .env is found
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        # Allow case-insensitive environment variable names
        case_sensitive = False

# Create the settings instance
settings = Settings()

# Backward compatibility: If ACCESS_TOKEN_EXPIRE_SECONDS is set in env, use it
# Otherwise, calculate from ACCESS_TOKEN_EXPIRE_MINUTES
# IMPORTANT: Only use env value if it's explicitly set and reasonable (< 1 hour for security)
# Otherwise, always calculate from ACCESS_TOKEN_EXPIRE_MINUTES to ensure consistency
if "ACCESS_TOKEN_EXPIRE_SECONDS" in os.environ:
    env_value = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", str(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)))
    # Only use env value if it's reasonable (less than 1 hour = 3600 seconds)
    # This prevents accidentally setting very long expiration times
    if env_value <= 3600:
        settings.ACCESS_TOKEN_EXPIRE_SECONDS = env_value
    else:
        # Env value is too large, calculate from minutes instead
        settings.ACCESS_TOKEN_EXPIRE_SECONDS = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
else:
    settings.ACCESS_TOKEN_EXPIRE_SECONDS = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

# Fallback CSRF_SECRET_KEY if not set (use SECRET_KEY with prefix)
if not settings.CSRF_SECRET_KEY:
    settings.CSRF_SECRET_KEY = f"csrf_{settings.SECRET_KEY}"

# Optional: test that values are loaded
print("DATABASE_URL:", settings.DATABASE_URL)
print("SECRET_KEY:", settings.SECRET_KEY)
print(f"Token Configuration:")
print(f"  - Access Token: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes ({settings.ACCESS_TOKEN_EXPIRE_SECONDS} seconds)")
refresh_token_minutes_web = settings.REFRESH_TOKEN_EXPIRE_DAYS_WEB * 60 * 24
refresh_token_minutes_mobile = settings.REFRESH_TOKEN_EXPIRE_DAYS_MOBILE * 60 * 24
print(f"  - Refresh Token (Web): {settings.REFRESH_TOKEN_EXPIRE_DAYS_WEB} days ({refresh_token_minutes_web:.1f} minutes)")
print(f"  - Refresh Token (Mobile): {settings.REFRESH_TOKEN_EXPIRE_DAYS_MOBILE} days ({refresh_token_minutes_mobile:.1f} minutes)")
max_session_minutes = settings.MAX_SESSION_LIFETIME_DAYS * 60 * 24
print(f"  - Max Session Lifetime: {settings.MAX_SESSION_LIFETIME_DAYS} days ({max_session_minutes:.1f} minutes)")
