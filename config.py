import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 86400

    # OTP config
    OTP_EXPIRY_SECONDS: int = 120  # 2 minutes
    OTP_MAX_REQUESTS_PER_HOUR: int = 15  # 15 per hour
    OTP_MAX_FAILED_ATTEMPTS: int = 5  # Block after 5 failed attempts
    OTP_BLOCK_DURATION_SECONDS: int = 600  # 10 minutes block

    ENVIRONMENT: str = "development"

    class Config:
        # Use absolute path to make sure .env is found
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"

# Create the settings instance
settings = Settings()

# Optional: test that values are loaded
print("DATABASE_URL:", settings.DATABASE_URL)
print("SECRET_KEY:", settings.SECRET_KEY)
