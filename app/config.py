from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./aicid.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORDLESS_API_TOKEN_EXPIRE_MINUTES: int = 30
    AUTH_CHALLENGE_EXPIRE_MINUTES: int = 15
    ENVIRONMENT: str = "development"

    APP_NAME: str = "AICID"
    APP_DESCRIPTION: str = "Unique identifiers for AI scientists and co-scientists"
    APP_URL: str = "https://aicid.net"
    EMAIL_FROM: str = "no-reply@aicid.net"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True


settings = Settings()
