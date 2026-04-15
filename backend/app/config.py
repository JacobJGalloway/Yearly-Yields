from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Anthropic
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    # SendGrid
    SENDGRID_API_KEY: str
    SENDGRID_FROM_EMAIL: str
    SENDGRID_FROM_NAME: str = "Yearly Yields"

    # NOAA
    NOAA_BASE_URL: str = "https://api.weather.gov"
    NOAA_USER_AGENT: str = "yearly-yields/0.1.0"

    # Alerts
    # How many hours must pass before a repeat email is sent for an active alert.
    # Default: 24h. Min: 4h (avoid spam). Max: 72h (3 days — ensure farmer awareness).
    ALERT_EMAIL_INTERVAL_HOURS: int = 24

    @field_validator("ALERT_EMAIL_INTERVAL_HOURS")
    @classmethod
    def validate_alert_interval(cls, v: int) -> int:
        if v < 4 or v > 72:
            raise ValueError("ALERT_EMAIL_INTERVAL_HOURS must be between 4 and 72")
        return v

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:4200"]


settings = Settings()
