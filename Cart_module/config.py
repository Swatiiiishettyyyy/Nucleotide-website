import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 86400

    # OTP config
    OTP_EXPIRY_SECONDS: int = 300
    OTP_MAX_REQUESTS_PER_HOUR: int = 5

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