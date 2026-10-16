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
    BROWSER_SESSION_EXPIRE_MINUTES: int = 30
    ENVIRONMENT: str = "development"

    APP_NAME: str = "AICID"
    APP_DESCRIPTION: str = "Unique identifiers for AI scientists and co-scientists"
    APP_URL: str = "https://aicid.net"
    EMAIL_FROM: str = "no-reply@aicid.net"
    POSTHORN_BASE_URL: str | None = None
    POSTHORN_API_KEY: str | None = None
    POSTHORN_PATH: str = "/api/send"
    # the relay answers only after its SMTP hand-off, observed at 6-21s
    POSTHORN_TIMEOUT_SECONDS: float = 45.0

    # anti-spam for the anonymous /register form
    SPAM_BLOCKED_EMAIL_DOMAINS: str = ""  # comma-separated, added to the built-in list
    REGISTRATION_LIMIT_PER_HOUR: int = 50
    REGISTRATION_LIMIT_PER_EMAIL_PER_HOUR: int = 10
    REGISTRATION_CONFIRM_EXPIRE_MINUTES: int = 24 * 60
    # agents registering themselves through POST /api/register (published at once)
    SELF_REGISTRATION_LIMIT_PER_HOUR: int = 20
    CLAIM_EMAIL_INTERVAL_MINUTES: int = 10
    CLAIM_EXPIRE_MINUTES: int = 24 * 60
    TEAM_EMAIL: str = "team@aicid.net"
    SESSION_COOKIE_NAME: str = "aicid_session"

    ORCID_CLIENT_ID: str | None = None
    ORCID_CLIENT_SECRET: str | None = None
    ORCID_REDIRECT_URI: str = "https://aicid.net/manage/orcid/callback"


settings = Settings()
