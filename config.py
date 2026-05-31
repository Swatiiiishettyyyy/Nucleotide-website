import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, model_validator


def _clean_env_value(value) -> str:
    return str(value or "").strip().strip('"').strip("'")


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    # Token configuration - Dual Token Strategy
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Default: 15 minutes
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900  # Will be recalculated from minutes if not set in env
    REFRESH_TOKEN_EXPIRE_DAYS_WEB: float = 7.0  # Default: 7 days
    REFRESH_TOKEN_EXPIRE_DAYS_MOBILE: float = 7.0  # Default: 7 days
    
    # Cookie configuration for web
    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool 
    # Cookie SameSite attribute: value must be provided via environment/.env
    COOKIE_SAMESITE: str
    # Separate SameSite setting for refresh token cookie
    REFRESH_COOKIE_SAMESITE: str
    
    # CSRF protection
    CSRF_SECRET_KEY: str = ""
    
    # OTP config - can be overridden via .env
    OTP_EXPIRY_SECONDS: int = 120  # 2 minutes
    OTP_MAX_REQUESTS_PER_HOUR: int = 15  # 15 per hour
    OTP_MAX_FAILED_ATTEMPTS: int = 5  # Block after 5 failed attempts
    OTP_BLOCK_DURATION_SECONDS: int = 600  # 10 minutes block

    # MSG91 configuration
    MSG91_AUTH_KEY: str = ""
    MSG91_OTP_TEMPLATE_ID: str = ""
    MSG91_WELCOME_SMS_TEMPLATE_ID: str = "69f44d91ddb266e8b80172a3"
    MSG91_SLOT_SELECTED_TEMPLATE_ID: str = "69f44ef4e1ffe4db810f7622"
    MSG91_REPORT_READY_TEMPLATE_ID: str = "69f44dbf9fe3b2ab780d5982"
    MSG91_FLOW_URL: str = "https://api.msg91.com/api/v5/flow/"
    MSG91_SHORT_URL: int = 0
    MSG91_REALTIME_RESPONSE: int = 1
    
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

    # Razorpay — set RAZORPAY_MODE=test or live; keys resolved at startup (see resolve_razorpay_keys)
    RAZORPAY_MODE: str = "test"
    RAZORPAY_TEST_KEY_ID: str = ""
    RAZORPAY_TEST_KEY_SECRET: str = ""
    RAZORPAY_TEST_WEBHOOK_SECRET: str = ""
    RAZORPAY_LIVE_KEY_ID: str = ""
    RAZORPAY_LIVE_KEY_SECRET: str = ""
    RAZORPAY_LIVE_WEBHOOK_SECRET: str = ""
    # Resolved from mode; also accepts legacy RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET / RAZORPAY_WEBHOOK_SECRET
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Twilio Verify API - for SMS verification (separate from custom OTP flow)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_VERIFY_SERVICE_SID: str = ""

    # Firebase FCM - path to service account JSON; empty = skip FCM send (notifications still stored in DB)
    FIREBASE_SERVICE_ACCOUNT_PATH: str = ""
    # When True (default), invalid FCM tokens are removed after failed send. When False (e.g. dev/test with dummy token), tokens are kept so notification trigger keeps running for every event.
    REMOVE_INVALID_FCM_TOKENS: bool = True

    # Invoice Generation & Sending
    INVOICE_SERVICE_ACCOUNT_PATH: str = "invoice generation/billing.json"
    INVOICE_SENDER_EMAIL: str = "billing@nucleotide.life"
    INFO_SENDER_EMAIL: str = "info@nucleotide.life"
    ORDER_TRACKING_BASE_URL: str = "https://www.nucleotide.life/track-order"
    INVOICE_COMPANY_NAME: str = "Nucleotide Healthcare Pvt Ltd"
    INVOICE_COMPANY_ADDRESS: str = "Bangalore, Karnataka, India"
    INVOICE_PAN_NUMBER: str = "AADCE5479M"
    INVOICE_SAC_CODE: str = "999312"
    INVOICE_CUSTOMER_CARE_PHONE: str = "+91 9403891587"
    INVOICE_CUSTOMER_CARE_EMAIL: str = "info@nucleotide.life"
    INVOICE_WEBSITE: str = "www.nucleotide.life"
    INVOICE_LOGO_PATH: str = "invoice generation/logo.png"
    # Comma-separated BCC addresses for invoice emails, e.g. "a@x.com,b@x.com"
    INVOICE_BCC_EMAILS: str = ""
    ORDER_CONFIRMATION_GIF_URL: str = "https://nucleotide-email-template.s3.ap-south-1.amazonaws.com/Delivery+Boy.gif"

    # Google Maps / reverse geocoding
    GOOGLE_MAPS_API_KEY: str = ""
    VITE_GOOGLE_MAPS_API_KEY: str = ""

    model_config = ConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra env vars not defined in Settings
    )

    @model_validator(mode="after")
    def resolve_razorpay_keys(self) -> "Settings":
        mode = (self.RAZORPAY_MODE or "test").strip().lower()
        if mode not in {"test", "live"}:
            raise ValueError("RAZORPAY_MODE must be either 'test' or 'live'")
        self.RAZORPAY_MODE = mode

        legacy_key_id = _clean_env_value(self.RAZORPAY_KEY_ID)
        legacy_secret = _clean_env_value(self.RAZORPAY_KEY_SECRET)
        legacy_webhook = _clean_env_value(self.RAZORPAY_WEBHOOK_SECRET)

        if mode == "live":
            self.RAZORPAY_KEY_ID = _clean_env_value(self.RAZORPAY_LIVE_KEY_ID) or legacy_key_id
            self.RAZORPAY_KEY_SECRET = _clean_env_value(self.RAZORPAY_LIVE_KEY_SECRET) or legacy_secret
            self.RAZORPAY_WEBHOOK_SECRET = (
                _clean_env_value(self.RAZORPAY_LIVE_WEBHOOK_SECRET) or legacy_webhook
            )
        else:
            self.RAZORPAY_KEY_ID = _clean_env_value(self.RAZORPAY_TEST_KEY_ID) or legacy_key_id
            self.RAZORPAY_KEY_SECRET = _clean_env_value(self.RAZORPAY_TEST_KEY_SECRET) or legacy_secret
            self.RAZORPAY_WEBHOOK_SECRET = (
                _clean_env_value(self.RAZORPAY_TEST_WEBHOOK_SECRET) or legacy_webhook
            )
        return self


# Create the settings instance
settings = Settings()


def _read_local_env_value(*names: str) -> str:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() in names:
                    return _clean_env_value(value.split(" #", 1)[0])
    except OSError:
        return ""
    return ""


def _first_config_value(*names: str) -> str:
    for name in names:
        value = _clean_env_value(getattr(settings, name, ""))
        if value:
            return value
    for name in names:
        value = _clean_env_value(os.getenv(name))
        if value:
            return value
    return _read_local_env_value(*names)


# Normalize MSG91 settings after BaseSettings loads. This covers local shells or
# process managers that accidentally export empty values and shadow .env.
settings.MSG91_AUTH_KEY = _first_config_value("MSG91_AUTH_KEY")
settings.MSG91_OTP_TEMPLATE_ID = _first_config_value(
    "MSG91_OTP_TEMPLATE_ID",
    "MSG91_TEMPLATE_ID_OTP",
    "MSG91_LOGIN_OTP_TEMPLATE_ID",
)
settings.MSG91_FLOW_URL = _first_config_value("MSG91_FLOW_URL") or settings.MSG91_FLOW_URL

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
