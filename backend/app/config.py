import re

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
    # Sliding window: rotate access token when its age exceeds this many seconds.
    # Set to 0 to disable rotation. Defaults to 30s to avoid thrashing on parallel
    # requests at login while still refreshing well before the 30-min expiry.
    TOKEN_ROTATION_THRESHOLD_SECONDS: int = 30

    # Anthropic
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    # SendGrid
    SENDGRID_API_KEY: str
    SENDGRID_FROM_EMAIL: str
    SENDGRID_FROM_NAME: str = "Yearly Yields"

    # NWS / NOAA
    NOAA_BASE_URL: str = "https://api.weather.gov"
    NOAA_USER_AGENT: str = "yearly-yields/0.1.0"
    NOAA_CDO_TOKEN: str = ""         # free token from ncei.noaa.gov/cdo-web/token (historical backfill)
    NWS_POLL_INTERVAL_HOURS: int = 4      # how often to poll NWS observations per active station
    FIOT_POLL_INTERVAL_HOURS: float = 2.0  # how often the fIoT loop generates greenhouse readings
    FIOT_TEMP_NOISE_STDDEV_F: float = 1.5  # Gaussian noise stddev for simulated temperature (°F)
    FIOT_HUMIDITY_NOISE_STDDEV_PCT: float = 3.0  # Gaussian noise stddev for simulated humidity (%)
    FIOT_DEFAULT_HUMIDITY_PCT: float = 65.0  # fallback target humidity when area.target_humidity_pct is null

    PURGE_INTERVAL_HOURS: int = 24  # how often the nightly sensor reading purge runs
    PHASE_CHECK_INTERVAL_HOURS: int = 24  # how often to check crop cycles for harvest phase entry

    # Data retention
    # Sensor readings older than this many days are hard-deleted by the nightly purge job.
    # Default: 1095 days (3 years). Min: 365. Max: 3650 (10 years).
    DATA_RETENTION_DAYS: int = 1095
    # Daily readings older than this many days are summarized into weekly_sensor_summaries
    # on each SUMMARIZATION_DATES run. Default: 90 days (~1 quarter).
    DAILY_RETENTION_DAYS: int = 90
    # MM-DD dates on which the summarization job runs (quarterly by default).
    SUMMARIZATION_DATES: list[str] = ["03-31", "06-30", "09-30", "12-31"]
    # Weekly sensor summaries older than this many years are purged each Dec 31.
    # Default: 5 years. Summaries are low-volume aggregates; keep longer than raw readings.
    WEEKLY_SUMMARY_RETENTION_YEARS: int = 5

    # Alerts
    # How many hours must pass before a repeat email is sent for an active alert.
    # Default: 24h. Min: 4h (avoid spam). Max: 72h (3 days — ensure farmer awareness).
    ALERT_EMAIL_INTERVAL_HOURS: int = 24

    # How many consecutive normal readings are required to resolve an active alert.
    # Default: 3. Min: 1. Max: 10.
    ALERT_RESOLUTION_THRESHOLD: int = 3

    @field_validator("SUMMARIZATION_DATES")
    @classmethod
    def validate_summarization_dates(cls, v: list[str]) -> list[str]:
        for entry in v:
            if not re.fullmatch(r"\d{2}-\d{2}", entry):
                raise ValueError(f"SUMMARIZATION_DATES entries must be MM-DD format, got {entry!r}")
        return v

    @field_validator("DATA_RETENTION_DAYS")
    @classmethod
    def validate_retention_days(cls, v: int) -> int:
        if v < 365 or v > 3650:
            raise ValueError("DATA_RETENTION_DAYS must be between 365 and 3650")
        return v

    @field_validator("ALERT_EMAIL_INTERVAL_HOURS")
    @classmethod
    def validate_alert_interval(cls, v: int) -> int:
        if v < 4 or v > 72:
            raise ValueError("ALERT_EMAIL_INTERVAL_HOURS must be between 4 and 72")
        return v

    @field_validator("ALERT_RESOLUTION_THRESHOLD")
    @classmethod
    def validate_resolution_threshold(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("ALERT_RESOLUTION_THRESHOLD must be between 1 and 10")
        return v

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:4200"]


settings = Settings()
